# VocalFusion Raspberry Pi Setup Change Log

## 5.2.0

  * Added copying of asoundrc file at bootup
  * Fixed checks for installation of debian packages
  * Updated equality operators

## 5.1.0

  * Added support for xvf3510-ua
  * Renamed xvf3510 device as xvf3510-int
  * Fix bug in parsing of device names
  * Install one Debian package at the time

## 5.0.0

  * Added support for xvf3610-ua and xvf3615-ua
  * Renamed xvf3615 device as xvf3615-int
  * Renamed xvf3610 device as xvf3610-int

## 4.3.1

  * Fix comments and reg names in setup_dac.py

## 4.3.0

  * Added support for xvf3610 EVK board
  * Removed support for xvf3610 development board

## 4.2.0

  * Added support for xvf3600.
  * Renamed I2S_CLK_DAC_SETUP flag to include I2S master configurations

## 4.1.0

  * Added support for xvf3610.

## 4.0.0

  * Change supported command line arguments. Instead of vocalfusion for 3100, nothing for 3500, and vxf3510 for 3510, arguments are now xvf3100 for 3100, xvf3500 for 3500, and xvf3510 for 3510.
  * Internal changes to support adding future products.

## 3.0.0

  * Update clock dividers for RPi3 to generate a 12.288MHz clock, since the RPi4 clock at 24.576MHz has glitches
  * Add support for RPi4 on I2S loader kernel module
  * Add delay in loading I2S drivers needed for Buster on RPi3
  * Add script compute_clock_dividers.py to compute dividers for MCLK and BCLK
  * Fix some indentations and general tidy up

## 2.3.0

  * Add support for 16kHz BCLK generation

## 2.2.0

  * Support runtime disabling of MCLK drive to allow for I2S role change

## 2.1.0

  * Enable SPI interface
  * Add installation of packages for dev kit

## 2.0.0

  * Use default I2C hardware
  * Add installation of Py3 packages

## 1.3.2

  * Added audacity installation and setup for XVF3510

## 1.3.1

  * Added reset for XVF3510

## 1.3.0

  * Added support for XVF3510
  * Modified I2S loader to be either master or slave

## 1.2.1

  * Remove BCM2708 modules that no longer exist in Stretch (#4)
  * Stop on kernel module build error
  * Require reinstall of kernel and firmware so kernel headers match running kernel version and we can build kernel modules (#6)

## 1.2.0

  * New ALSA configurations for both VocalFusion and VocalFusion Stereo devices.
  * Optional setup.sh argument to specify VocalFusion ALSA configuration.

## 1.1.0

  * Updated I2C driver to be compatible with Linux Kernel v4.10.

## 1.0.0

  * Moved to vocalfusion-rpi-setup repo.
  * Removed the need to download Linux Raspberry Pi source code.
  * Removed snd_driver/bclk_patch.
