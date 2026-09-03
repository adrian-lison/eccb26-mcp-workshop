#!/usr/bin/env python3

import sys
from json import load
from pathlib import Path
from subprocess import run
from typing import Annotated
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
    ] = 100
) -> dict:
    """
    Returns the number of sequences matching the specified sequence filters, grouped by amino acid mutations. Additionally, the relative frequency of each mutation is returned. It is relative to the total number of sequences matching the specified sequence filters with non-ambiguous reads at that position.
    """
    print(
        "Tool amino acid mutation search called with parameters: "
        f"filter_country={filter_country}, minProportion={minProportion}, limit={limit}",
        file=sys.stderr,
    )

    query_parameters = {}
    if filter_country is not None:
        query_parameters["country"] = filter_country
    if minProportion is not None:
        query_parameters["minProportion"] = minProportion
    if limit is not None:
        query_parameters["limit"] = limit

    url = (
        "https://lapis.cov-spectrum.org/open/v2/sample/aminoAcidMutations"
        f"?{urlencode(query_parameters)}"
    )

    try:
        with urlopen(url, timeout=20) as response:
            result = load(response)
    except HTTPError as error:
        return {"error": f"Could not retrieve mutations (HTTP {error.code})."}
    except URLError as error:
        return {"error": "Could not retrieve mutations."}

    mutations = result["data"]
    n_results = len(mutations)

    note = f"Returned {n_results} of a maximum {limit} results."
    if n_results == limit:
        note += " There could be more results available beyond this limit."

    return {
        "mutations": mutations,
        "note": note,
    }

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
