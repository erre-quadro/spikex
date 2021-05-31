import sys
import os

from subprocess import run
from wasabi import msg


WG_LATEST_TABLE = {
    "enwiki_core": "enwiki_core-20210520",
    "simplewiki_core": "simplewiki_core-20210520",
    "itwiki_core": "itwiki_core-20210520",
}

WG_TABLE = {
    "enwiki_core-20210520": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EeIb238HAmtCruMvhzZdOl8BIEBU_09XV5FnHE4SVmYzBQ?Download=1",
    "simplewiki_core-20210520": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EWdpEV_R4JVEk_ZwvJTrAEUBsLpmJMxyWDa13sFOzQAo3Q?Download=1",
    "itwiki_core-20210520": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EcWYGXp5SUdGvFTHN9KQ_zkBW8Zu9p0hiwpC3oKyhibXtQ?Download=1",

    "enwiki_core-20210401": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/Eco6n99fPu5NktUaF7SkzpkBk7Ru3ZaH-BD_tr8Tq6sHWw?Download=1",
    "simplewiki_core-20210401": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EbwV-u0YtVdNo4f02X7HbDsBs3BRTEu4ix-_n0JYLKOJzQ?Download=1",
    "itwiki_core-20210401": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EY7anrn0R0JApoIryZck2b0Bl6T_o3YGNAbCpg6eAHXPrg?Download=1",

    "enwiki_core-20210201": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/ESedYiVvufpCtImuOlFXm6MB_5YyfKQnZIvDinnYbL-NmA?Download=1",
    "simplewiki_core-20210201": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EQhheXcD9KtGpXyoZ9a2zOEBmGIvZXuyFoV1KoYOzgsjLw?Download=1",
    "itwiki_core-20210201": "https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EVBnV0JaBNlFpmNg91hT458BfFjY_7MW2kqIvRCkhdpWVQ?Download=1",
}


def download_wikigraph(wg_name: str):
    """
    Download and install a `WikiGraph`.

    Parameters
    ----------
    wg_name : str
        Name of the `WikiGraph` to download.
    """
    wg_name = WG_LATEST_TABLE.get(wg_name, wg_name)
    wg_url = WG_TABLE.get(wg_name)
    if wg_url is None:
        msg.fail(
            f"{wg_name} not available yet. Try with: {', '.join(WG_TABLE)}",
            exits=1,
        )
    wg_tar = f"{wg_name}.tar.gz"
    _run_command(f"wget --quiet --show-progress -O {wg_tar} {wg_url}")
    _run_command(
        f"{sys.executable} -m pip install --no-deps --force-reinstall --no-cache-dir {wg_tar}"
    )
    _run_command(f"rm {wg_tar}")


def _run_command(command):
    return run(
        command.split(),
        env=os.environ.copy(),
        encoding="utf8",
        check=False,
    )