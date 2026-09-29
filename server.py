#!/usr/bin/env python3
from __future__ import annotations
import sys
from datetime import date
from json import load
from pathlib import Path
from subprocess import run
from typing import Annotated, Literal, TypeAlias
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from mcp.server import MCPServer
from pydantic import Field, BaseModel, ConfigDict, model_validator

# Create the MCP server.
mcp = MCPServer("lapis-demo")


# Exact-match API fields accept either one value or a non-empty OR-list.
ExactFloat: TypeAlias = float | Annotated[list[float], Field(min_length=1)]
ExactInt: TypeAlias = int | Annotated[list[int], Field(min_length=1)]
ExactString: TypeAlias = str | Annotated[list[str], Field(min_length=1)]
ExactDate: TypeAlias = date | Annotated[list[date], Field(min_length=1)]


class SequenceFilter(BaseModel):
    """
    Criteria used to select sequence records.

    All supplied fields are combined with AND. For exact-match fields, passing
    a list means that any listed value may match (logical OR).
    """

    model_config = ConfigDict(
        extra="forbid",        # Reject unknown/hallucinated filter names
        populate_by_name=True,
        allow_inf_nan=False,  # Reject NaN and infinity for floating values
    )

    ace2_binding: Annotated[
        ExactFloat | None,
        Field(
            default=None,
            alias="ace2Binding",
            description=(
                "Exact ACE2-binding value, or a non-empty list of exact "
                "values. A list is combined with OR."
            ),
        ),
    ]

    ace2_binding_from: Annotated[
        float | None,
        Field(
            default=None,
            alias="ace2BindingFrom",
            description="Minimum ACE2-binding value, inclusive.",
        ),
    ]

    ace2_binding_to: Annotated[
        float | None,
        Field(
            default=None,
            alias="ace2BindingTo",
            description="Maximum ACE2-binding value, inclusive.",
        ),
    ]

    age: Annotated[
        ExactInt | None,
        Field(
            default=None,
            description=(
                "Exact age, or a non-empty list of accepted exact ages. "
                "A list is combined with OR."
            ),
        ),
    ]

    age_from: Annotated[
        int | None,
        Field(
            default=None,
            alias="ageFrom",
            ge=0,
            description="Minimum age, inclusive.",
        ),
    ]

    age_to: Annotated[
        int | None,
        Field(
            default=None,
            alias="ageTo",
            ge=0,
            description="Maximum age, inclusive.",
        ),
    ]

    authors: Annotated[
        ExactString | None,
        Field(
            default=None,
            description=(
                "Exact author name, or a non-empty list of accepted authors. "
                "A list is combined with OR."
            ),
        ),
    ]

    authors_regex: Annotated[
        str | None,
        Field(
            default=None,
            alias="authorsRegex",
            min_length=1,
            description=(
                "Regular expression for author matching. Prefer `authors` "
                "when exact matching is sufficient."
            ),
        ),
    ]

    country: Annotated[
        ExactString | None,
        Field(
            default=None,
            description=(
                "Exact country value, or a non-empty list of accepted countries. "
                "A list is combined with OR."
            ),
        ),
    ]

    country_regex: Annotated[
        str | None,
        Field(
            default=None,
            alias="countryRegex",
            min_length=1,
            description=(
                "Regular expression for country matching. Prefer `country` "
                "when exact matching is sufficient."
            ),
        ),
    ]

    country_exposure: Annotated[
        ExactString | None,
        Field(
            default=None,
            alias="countryExposure",
            description="Exact exposure country, or a non-empty OR-list.",
        ),
    ]

    country_exposure_regex: Annotated[
        str | None,
        Field(
            default=None,
            alias="countryExposureRegex",
            min_length=1,
            description="Regular expression for exposure-country matching.",
        ),
    ]

    database: Annotated[
        ExactString | None,
        Field(
            default=None,
            description="Exact database name, or a non-empty OR-list.",
        ),
    ]

    database_regex: Annotated[
        str | None,
        Field(
            default=None,
            alias="databaseRegex",
            min_length=1,
            description="Regular expression for database matching.",
        ),
    ]

    collection_date: Annotated[
        ExactDate | None,
        Field(
            default=None,
            alias="date",
            description=(
                "Exact collection date, or a non-empty list of dates, in "
                "YYYY-MM-DD format."
            ),
        ),
    ]

    date_from: Annotated[
        date | None,
        Field(
            default=None,
            alias="dateFrom",
            description="Earliest collection date, inclusive, in YYYY-MM-DD format.",
        ),
    ]

    date_to: Annotated[
        date | None,
        Field(
            default=None,
            alias="dateTo",
            description="Latest collection date, inclusive, in YYYY-MM-DD format.",
        ),
    ]

    usher_tree_phylo_descendant_of: Annotated[
        ExactString | None,
        Field(
            default=None,
            alias="usherTreePhyloDescendantOf",
            description=(
                "Exact usher-tree node ID, or a non-empty list of node IDs, "
                "restricting results to descendants of that node in the "
                "usher phylogenetic tree. A list is combined with OR."
            ),
        ),
    ]

    @model_validator(mode="after")
    def validate_semantics(self) -> "SequenceFilter":
        if self.age_from is not None and self.age_to is not None:
            if self.age_from > self.age_to:
                raise ValueError("ageFrom must be less than or equal to ageTo")

        if (
            self.ace2_binding_from is not None
            and self.ace2_binding_to is not None
            and self.ace2_binding_from > self.ace2_binding_to
        ):
            raise ValueError(
                "ace2BindingFrom must be less than or equal to ace2BindingTo"
            )

        if self.date_from is not None and self.date_to is not None:
            if self.date_from > self.date_to:
                raise ValueError("dateFrom must be on or before dateTo")

        # This is a product decision. Reject it if exact and regex matching
        # for the same column would be confusing or redundant.
        if self.country is not None and self.country_regex is not None:
            raise ValueError("Use either country or countryRegex, not both")

        if self.authors is not None and self.authors_regex is not None:
            raise ValueError("Use either authors or authorsRegex, not both")

        if self.database is not None and self.database_regex is not None:
            raise ValueError("Use either database or databaseRegex, not both")

        if (
            self.country_exposure is not None
            and self.country_exposure_regex is not None
        ):
            raise ValueError(
                "Use either countryExposure or countryExposureRegex, not both"
            )

        return self

def to_upstream_filter(filter: SequenceFilter) -> dict[str, object]:
    # `by_alias=True` produces the MCP/API-friendly camelCase field names,
    # and `mode="json"` converts `date` instances to YYYY-MM-DD strings.
    payload = filter.model_dump(
        by_alias=True,
        exclude_none=True,
        mode="json",
    )

    dotted_names = {
        "authorsRegex": "authors.regex",
        "countryRegex": "country.regex",
        "countryExposureRegex": "countryExposure.regex",
        "databaseRegex": "database.regex",
        "usherTreePhyloDescendantOf": "usherTree.phyloDescendantOf",
    }

    return {
        dotted_names.get(key, key): value
        for key, value in payload.items()
    }


@mcp.tool(title="STRING: Get statistics on amino acid mutations")
def get_amino_acid_mutations(
    filter: SequenceFilter,
    minProportion: Annotated[
        float,
        Field(
            description="Optional. Minimum proportion at which mutations are reported.",
            ge=0,
            le=1,
        ),
    ] = None,

    limit: Annotated[
        int,
        Field(
            description="The maximum number of entries to return in the response. Default is 100.",
            ge=1,
            le=20
        )
    ] = 10,
    orderBy: Annotated[
        list[Literal["mutation", "count", "coverage", "proportion", "position", "random"]],
        Field(
            description=(
                "Optional. One or several fields to order the results by, sorted "
                "in ascending (not descending) order. Leave empty to use the "
                "default order. If ordering is desired but no field is "
                "specified by the user, default to 'proportion'."
            ),
        ),
    ] = None,
) -> dict:
    """
    Returns the number of sequences matching the specified sequence filters, grouped by amino acid mutations. Additionally, the relative frequency of each mutation is returned. It is relative to the total number of sequences matching the specified sequence filters with non-ambiguous reads at that position.
    """
    filters=to_upstream_filter(filter)
    print(
        "Tool amino acid mutation search called with parameters: "
        f"filters={filters}, minProportion={minProportion}, limit={limit}, "
        f"orderBy={orderBy}",
        file=sys.stderr,
    )

    query_parameters = {}
    if filters:
        query_parameters.update(filters)
    if minProportion is not None:
        query_parameters["minProportion"] = minProportion
    if limit is not None:
        query_parameters["limit"] = limit
    if orderBy:
        query_parameters["orderBy"] = orderBy

    url = (
        "https://lapis.cov-spectrum.org/open/v2/sample/aminoAcidMutations"
        f"?{urlencode(query_parameters, doseq=True)}"
    )
    print(f"Request URL: {url}", file=sys.stderr)

    try:
        with urlopen(url, timeout=20) as response:
            result = load(response)
    except HTTPError as error:
        response_dict = {"error": f"Could not retrieve mutations (HTTP {error.code})."}
        print(f"Response: {response_dict}", file=sys.stderr)
        return response_dict
    except URLError as error:
        response_dict = {"error": "Could not retrieve mutations."}
        print(f"Response: {response_dict}", file=sys.stderr)
        return response_dict

    print(f"Raw response body: {result}", file=sys.stderr)

    mutations = result["data"]
    n_results = len(mutations)

    note = f"Returned {n_results} of a maximum {limit} results."
    if n_results == limit:
        note += " There could be more results available beyond this limit."

    response_dict = {
        "mutations": mutations,
        "note": note,
    }
    print(f"Response: {response_dict}", file=sys.stderr)
    return response_dict

@mcp.tool(title="STRING: Get most recent common ancestor")
def get_mrca(filter: SequenceFilter) -> dict:
    """
    Returns the most recent common ancestor (MRCA) of sequences matching the
    specified sequence filters, based on the usher phylogenetic tree. If
    sequences included in the filter do not exist in the tree, they are
    ignored and their count is added to the field `missingNodeCount`.
    """
    filters = to_upstream_filter(filter)
    print(
        f"Tool MRCA search called with parameters: filters={filters}",
        file=sys.stderr,
    )

    query_parameters = dict(filters)
    query_parameters["phyloTreeField"] = "usherTree"
    query_parameters["printNodesNotInTree"] = "false"

    url = (
        "https://lapis.cov-spectrum.org/open/v2/sample/mostRecentCommonAncestor"
        f"?{urlencode(query_parameters, doseq=True)}"
    )
    print(f"Request URL: {url}", file=sys.stderr)

    try:
        with urlopen(url, timeout=20) as response:
            result = load(response)
    except HTTPError as error:
        response_dict = {"error": f"Could not retrieve MRCA (HTTP {error.code})."}
        print(f"Response: {response_dict}", file=sys.stderr)
        return response_dict
    except URLError as error:
        response_dict = {"error": "Could not retrieve MRCA."}
        print(f"Response: {response_dict}", file=sys.stderr)
        return response_dict

    print(f"Raw response body: {result}", file=sys.stderr)

    response_dict = {
        "data": result["data"],
        "note": (
            "The mrcaNode value is a node ID from the usher tree. It can be "
            "used in other queries/tools via the filter field "
            "'usherTree.phyloDescendantOf'."
        ),
    }
    print(f"Response: {response_dict}", file=sys.stderr)
    return response_dict


if __name__ == "__main__":
    
    try:
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=8000,
            stateless_http=True,
        )
    except KeyboardInterrupt:
        pass
