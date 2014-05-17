# image-disc

A small utility for making archival copies of CDs and DVDs under Linux. It runs in a terminal, and is meant for batch operation. Enter a disc name, pop in a disc, wait, take out the disc, rinse repeat. The script will continue asking for new discs until you hit `ctrl+C`.

There's a lot of duct tape in here, but it generally works. You've been warned.

Pull requests welcome, but please keep in mind that the purpose of this script is *archival-quality* copies where possible.

## Supported disc types

* Data CD-ROM
* Mixed-content CD-ROM (eg. data + audio)
* Audio-DVD
* Video-DVD
* Data DVD-ROM

## Unsupported disc types

* Audio-CD (use a secure ripper such as [Rubyripper](http://wiki.hydrogenaudio.org/index.php?title=Rubyripper) for this!)
* Bluray
* HD-DVD
* Other non-CD/DVD disc types

## Dependencies

You must have the following installed:

* Python
* cdrdao
* `ddrescue` (*not* `dd_rescue`!)
* UDisks (shipped by most distributions)
* `eject` (shipped by most distributions)
* udev (available in recent Linux kernels)

## Usage

`python image.py DEVICE TARGET [--ddrescue]`

* **DEVICE**: The source device to image from. This will be something like `/dev/sr0` or `/dev/cdrom`.
* **TARGET**: The target directory to place images in. Each image will be named according to the name you enter for that disc.
* **--ddrescue**: Optional flag to force the script to use ddrescue, even for (potential mixed-content) CD-ROMs. Useful for recovering damaged CD-ROMs. **This flag must always be *after* the device and target!**

## Remarks

This is duct tape. It ties together a bunch of existing utilities to automate your imaging. There is no guarantee that it'll work, or even that it'll produce valid images (although it will certainly try). **Check the integrity of your images, if you care about your data!**

The script is quite noisy; it doesn't try to understand output from utilities, and just passes it through wholesale. All messages originating from the script itself are prefixed with `##`.

Don't be alarmed if you get mounting/unmounting/eject failures; to avoid race conditions, the script is quite aggressive in making sure everything is unmounted/ejected when necessary. If you get errors, that usually just means that the disc was *already* unmounted or ejected.