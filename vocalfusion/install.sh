#!/usr/bin/env bash

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

vf_dir="${this_dir}/vocalfusion-rpi-setup-5.2.0"
install_dir='/usr/local/mycroft/mark-2'

# -----------------------------------------------------------------------------
# Copy files
# -----------------------------------------------------------------------------
ko_file="${vf_dir}/loader/i2s_master/i2s_master_loader.ko"
if [ ! -f "${ko_file}" ]; then
    echo "ERROR: Missing kernel object file (${ko_file}). Did you run 'make build'?"
    exit 1;
fi

sudo install -D \
    -t "${install_dir}" \
    "${ko_file}" \
    "${vf_dir}/resources/clk_dac_setup/setup_mclk" \
    "${vf_dir}/resources/clk_dac_setup/setup_bclk" \
    "${this_dir}/setup_microphone.py" \
    "${this_dir}/setup_speakers.py" \
    "${this_dir}/run.sh" \
    "${this_dir}/app_xvf3510_int_spi_boot_v4_2_0.bin"

sudo install -D \
    "${vf_dir}/resources/asoundrc_vf_xvf3510_int" \
    '/etc/alsa/conf.d/20-xmos.conf'

# -----------------------------------------------------------------------------
# Update config.txt in boot partition
# -----------------------------------------------------------------------------

config='/boot/config.txt'

# Disable the built-in audio output so there is only one audio device in the system
sudo sed -i -e 's/^dtparam=audio=on/#dtparam=audio=on/' "${config}"

# Enable the i2s device tree
sudo sed -i -e 's/#dtparam=i2s=on/dtparam=i2s=on/' "${config}"

# Enable the I2C device tree
sudo raspi-config nonint do_i2c 1
sudo raspi-config nonint do_i2c 0

# Set the I2C baudrate to 100k
sudo sed -i -e '/^dtparam=i2c_arm_baudrate/d' "${config}"
sudo sed -i -e 's/dtparam=i2c_arm=on$/dtparam=i2c_arm=on\ndtparam=i2c_arm_baudrate=100000/' "${config}"

# Enable the SPI support
sudo raspi-config nonint do_spi 1
sudo raspi-config nonint do_spi 0

# -----------------------------------------------------------------------------
# Create service to run on boot
# -----------------------------------------------------------------------------

sudo install \
    -t '/usr/lib/systemd/system' \
    "${this_dir}/etc/mark2-microphone.service"

sudo systemctl daemon-reload
sudo systemctl enable mark2-microphone


# -----------------------------------------------------------------------------

echo 'Installation successful. Please reboot.'
