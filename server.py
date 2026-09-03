#!/usr/bin/env python3

import sys
from json import load
from pathlib import Path
from subprocess import run
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from mcp.server import MCPServer
from pydantic import Field


HUMAN_PROTEIN_DATA_DIRECTORY = Path(__file__).parent / "data"
HUMAN_BIOLOGICAL_PROCESS_TERMS = (
    HUMAN_PROTEIN_DATA_DIRECTORY / "9606.protein.enrichment.terms.v12.0.txt"
)
HUMAN_BIOLOGICAL_PROCESS_TERMS_URL = (
    "https://stringdb-downloads.org/download/protein.enrichment.terms.v12.0/"
    "9606.protein.enrichment.terms.v12.0.txt.gz"
)


# Create the MCP server.
mcp = MCPServer("lapis-demo")


@mcp.tool(title="STRING: Get statistics on amino acid mutations")
def get_amino_acid_mutations(
    filter_country: Annotated[
        str,
        Field(
            description=(
                "Country to filter by. Leave empty to not filter by country."
            ),
            examples=["Switzerland", "United States"]
        ),
    ] = None,
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
            ge=1
        )
    ] = 100,
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
    print(
        "Tool amino acid mutation search called with parameters: "
        f"filter_country={filter_country}, minProportion={minProportion}, limit={limit}, "
        f"orderBy={orderBy}",
        file=sys.stderr,
    )

    query_parameters = {}
    if filter_country is not None:
        query_parameters["country"] = filter_country
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
