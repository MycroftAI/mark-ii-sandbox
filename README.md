# Mark II Sandbox

Builds a working base image for the Mark II based on Raspberry Pi OS.


## Prerequisites

* Docker with [buildkit](https://docs.docker.com/develop/develop-images/build_enhancements/)
* udisksctl
* sfdisk
* rsync


## Steps to Build

1. Download/extract a Raspberry Pi 64-bit Lite image to the `raspberry-pi-os` directory
2. In `raspberry-pi-os`, run `img2tar.py -i <img-file>` to create `p1.tar` and `p2.tar`
3. Fetch submodules for build:
   ```
   git submodule init
   git submodule update
   ```
4. In the root directory, run `make`
5. Run `sudo ./update-image.sh`
6. Burn `custom.img`

Once you've completed steps 1 and 2, you can run steps 3-5 after any changes to the Dockerfile.


## How it Works

This splits a Raspberry Pi OS image into boot/user partitions (`p1.tar` and `p2.tar` respectively). 
It then runs the Docker build with the user partition (`p2.tar`) as the base file system, allowing for software to be installed, etc.

Finally, `update-image.sh` recombines the original boot parition (`p1.tar`) with the result of the Docker build. This uses the files in the `boot` to overwrite `/boot` in the image (e.g., with `config.txt`).


### Partition Size

**NOTE**: depending on how much stuff you install during the Docker build, you may need to adjust the `raspberry-pi-os/partition_table.txt` file. The `size` of the second partition (`type=83`) may need to be increased before you run `update-image.sh`. Remember that this size is in *sectors* of 512 bytes. Lastly, ensure that the `custom_image_bytes` in `update-image.sh` is large enough to accomodate your new parition size.


## Installed Software

The following software is installed on top of the base Raspberry Pi OS:

* XMOS [VocalFusion](https://github.com/xmos/vocalfusion-rpi-setup) drivers for the microphone (XVF3510-INT)
    * This includes a pre-compiled kernel module (`i2s_master_loader`); you can re-build this module by running `make` in the `vocalfusion` directory on a Raspberry Pi.
* A DBus HAL service and commands that allow you do interact with the Mark II hardware
    * `mark2-leds R1,G1,B1,R2,G2,B2,...` lets you set the color(s) of the LEDs (0-255)
        * `mark2-leds <colors> <brightness>` also works (0-100)
    * `mark2-fan <percent>` lets you set the fan speed (0-100)
    * `mark2-volume <percent>` lets you set the amplifier volume (0-100)
    * `mark2-buttons` prints on/off events for the 3 buttons and 1 switch
* A service that runs `/usr/local/mycroft/mark-2/boot.sh` on boot
    * Turns off the LEDS
    * Sets fan to 50%
    * Sets volume to 60%
    
Additionally, I2C and SPI are enabled by default (required for the Mark II hardware).


## Docker Build

Building requires [Docker BuildKit](https://docs.docker.com/develop/develop-images/build_enhancements/). This is used to build for the `arm64` platform as well as cache apt/python packages so they can be reused across multiple builds.

To bootstrap your machine for the first build, ensure that you have qemu "binformat" support:

``` sh
sudo apt-get install binfmt-support
```

Then, create a Docker "builder" that supports multi-platform builds:

``` sh
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx create --use --name mybuilder
docker buildx use mybuilder
docker buildx inspect --bootstrap
```

After that, you should be able to run `make <TARGET>` to build one of the images (e.g., `make dinkum`).
