# mpc-scryfall

_Adapted from [woogerboy21/mpc-scryfall](https://github.com/woogerboy21/mpc-scryfall)._

Simple tool to retrieve Scryfall scans of MTG cards, upscale the image using `upscayl` (open source free local upscayler), and remove the copyright to get the image ready for MPC.

## Requirements

- Basic knowledge on how to run Python.
- An internet connection (it uses Scryfall).
- An installation of [Upscayl](https://upscayl.org/download) and the locaton of the binary `upscayl-bin`.
- Location of the model you want to use to upscale the cards. [Models](https://github.com/xinntao/Real-ESRGAN)

## Usage Guide

1. Install the python packages listed in `requirements.txt`.
1. List all the cards that you want to download in the `cards.txt` file at the root of the repository.
1. Run `python scryfall_formatter.py` optionally you can give it a parameter to create a new directory for the upscayled images i.e. `python scryfall_formatter.py Gwenom`.

### How to Search for a Specific Version or Set of a Card

**Set-specific searches**: To search within a particular set, add `s:` after the card name followed by the set code.

- Example: `Arcane Signet s:FIC`.

**Version-specific searches**: To select a specific version, use both `s:` for the set followed by `cn:` for the version number after the card name.

- Example: `Yuriko, the Tiger's Shadow s:CMM cn:690`

### Why are output images from Replicate cached?

In case you want to modify the posprocessing logic for every script execution. For example, you might decide that you want to use a different way of removing the copyright and the holographic stamp.

## Notes

- Retro cards can be imported but the copyright is not removed
- Full art cards cannot be extended unless they have black borders, if you try full art cards entended borders will overlap with the artwork.
