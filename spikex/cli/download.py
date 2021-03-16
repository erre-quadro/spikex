import sys

from spacy.util import run_command
from wasabi import msg

WIKIGRAPHS_TABLE = {
    "enwiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/ESedYiVvufpCtImuOlFXm6MB_5YyfKQnZIvDinnYbL-NmA?Download=1",
    "simplewiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EQhheXcD9KtGpXyoZ9a2zOEBmGIvZXuyFoV1KoYOzgsjLw?Download=1",
    "itwiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EVBnV0JaBNlFpmNg91hT458BfFjY_7MW2kqIvRCkhdpWVQ?Download=1",
}


def download_wikigraph(wg_name: str):
    """
    Download and install a `WikiGraph`.

    Parameters
    ----------
    wg_name : str
        Name of the `WikiGraph` to download.
    """
    if wg_name not in WIKIGRAPHS_TABLE:
        msg.fail(
            f"{wg_name} not available yet. Try with: {', '.join(WIKIGRAPHS_TABLE)}",
            exits=1,
        )
    wg_tar = f"{wg_name}.tar.gz"
    run_command(f"wget -O {wg_tar} {WIKIGRAPHS_TABLE[wg_name]}")
    run_command(
        f"{sys.executable} -m pip install --no-deps --force-reinstall --no-cache {wg_tar}"
    )
    run_command(f"rm {wg_tar}")
