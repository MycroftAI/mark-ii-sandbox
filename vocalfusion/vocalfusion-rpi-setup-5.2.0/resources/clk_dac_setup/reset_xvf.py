# Copyright (c) 2019-2021, XMOS Ltd, All rights reserved

import argparse
import smbus

def reset(args):
    """
    Function to reset XVF boards

    Args:
        args - command line arguments

    Returns:
        None
    """
    bus = smbus.SMBus(1)

    state = {}
    for i in [2, 6]:
        state[i] = bus.read_byte_data(0x20, i)

    # start reset
    data_to_write = 0x00 | (state[2] & 0xDF)
    bus.write_byte_data(0x20, 2, data_to_write)
    data_to_write = 0x00 | (state[6] & 0xDF)
    bus.write_byte_data(0x20, 6, data_to_write)

    # stop reset
    data_to_write = 0x20 | (state[2] & 0xDF)
    bus.write_byte_data(0x20, 2, data_to_write)
    data_to_write = 0x20 | (state[6] & 0xDF)
    bus.write_byte_data(0x20, 6, data_to_write)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hw", help="Hardware type")
    reset(parser.parse_args())
