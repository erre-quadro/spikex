import sys

from spacy.util import run_command
from wasabi import msg

WIKIGRAPHS_TABLE = {
    "enwiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/Eco6n99fPu5NktUaF7SkzpkBk7Ru3ZaH-BD_tr8Tq6sHWw?Download=1",
    "simplewiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EbwV-u0YtVdNo4f02X7HbDsBs3BRTEu4ix-_n0JYLKOJzQ?Download=1",
    "itwiki_core": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EY7anrn0R0JApoIryZck2b0Bl6T_o3YGNAbCpg6eAHXPrg?Download=1",
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
        f"{sys.executable} -m pip install --no-deps --force-reinstall --no-cache-dir {wg_tar}"
    )
    run_command(f"rm {wg_tar}")
