#!/bin/python3
from pynq import Overlay
from math import log2, floor

REG_MAX_COUNT = 41
REG_IO_INIT = 40
ADDR_OFFSET = 4
CLOCK_PERIOD = 8e-9
NUM_OUTPUT = 20  # number of used IO ports
NUM_CHANNELS = 10


class JvoAxiioDriver:
    def __init__(self,
                 bitfile='/home/xilinx/pynq/overlays/jvo6-axiio/axiio1_19.bit',
                 axiinput='jvo_axiinput_0'):
        overlay = Overlay(bitfile)
        self.io = getattr(overlay, axiinput)

    def write_reg(self, reg: int, value: int):
        """
        Write to a register by register number
        :param reg: reg number
        :param value: value to write as int
        :return:
        """
        if reg > 41:
            raise Exception('This reg is not available, maximum reg number is 41.')
        self.io.write(ADDR_OFFSET * reg, value)

    def set_reprate_seconds(self, seconds: float):
        """
        Set reprate in seconds
        :param seconds: reprate
        :return:
        """
        if seconds < 0:
            raise Exception('Value cannot be negative!')
        num_cycles = round(seconds / CLOCK_PERIOD)
        if log2(num_cycles) > 32:
            max_reprate = (2 ** 32 - 1) * CLOCK_PERIOD
            raise Exception('Number too large, maximum length is {} seconds.'.format(max_reprate))
        self.set_reprate_cycles(num_cycles)

    def set_reprate_cycles(self, num_cycles: int):
        """
        Set reprate as number of cycles
        :param num_cycles:
        :return:
        """
        self.reprate_cycles = num_cycles
        self.write_reg(REG_MAX_COUNT, num_cycles)

    def set_io_init(self, initial: str):
        """
        String with 1 and 0 to specify initial behavior of ports

        :param initial:
        :return:
        """
        if len(initial) != NUM_OUTPUT:
            raise Exception('String length has to be {}. It is now {}'.format(NUM_OUTPUT, len(initial)))
        try:
            initial_num = int(initial, 2)
        except TypeError:
            raise Exception('Please give input as string.')
        except ValueError:
            raise Exception('String should consist of only 1 and 0.')
        self.write_reg(REG_IO_INIT, initial_num)

    def set_output_cycles(self, output: str, start: int, stop: int):
        """
        Set start and stop time of output by number of cycles

        :param output: number of output as str 1a, 1b, 2a etc.
        :param start:
        :param stop:
        :return:
        """
        io_num = 4 * (int(output[:-1]) - 1)  # all but last char should be numeric
        io_offset = 2 if output[-1] == 'b' else 0
        if start > self.reprate_cycles:
            raise Exception('Start number is larger than rep. rate. This is not possible.')
        if stop > self.reprate_cycles:
            raise Exception('Stop number is larger than rep. rate. This is not possible.')
        if stop < start:
            raise Exception('Stop number should be larger than start number.')
        if stop == start:
            raise Exception('Stop number should not be equal to start number.')
        self.write_reg(io_num + io_offset, stop)
        self.write_reg(io_num + io_offset + 1, start)

    def set_output_seconds(self, output: str, start: float, stop: float):
        """
        Set the start and stop time for an output

        :param start:
        :param stop:
        :return:
        """
        num_cycles_start = round(start / CLOCK_PERIOD)
        num_cycles_stop = round(stop / CLOCK_PERIOD)
        # print('Setting start to {} and stop to {} cycles'.format(num_cycles_start, num_cycles_stop))
        self.set_output_cycles(output, num_cycles_start, num_cycles_stop)

    def loop_light(self, seconds: float, reverse: bool = False):
        """
        Make a loop light effect
        :param seconds:
        :param reverse: Change polarity
        :return:
        """
        self.set_io_init(NUM_OUTPUT * str(int(not reverse)))

        self.set_reprate_seconds(seconds)
        time_per_led = seconds / NUM_CHANNELS
        for i in range(0, NUM_CHANNELS):
            self.set_output_seconds('{}a'.format(i + 1), i * time_per_led, i * time_per_led + time_per_led)
            self.set_output_seconds('{}b'.format(i + 1), i * time_per_led, i * time_per_led + time_per_led)

    def progress_bar(self, seconds: float, reverse: bool = False):
        """
        Progress bar effect

        :param seconds:
        :param reverse: Change polarity
        :return:
        """
        self.set_io_init(NUM_OUTPUT * str(int(not reverse)))
        self.set_reprate_seconds(seconds)
        time_per_led = seconds / NUM_CHANNELS
        for i in range(0, NUM_CHANNELS):
            self.set_output_seconds('{}a'.format(i + 1), i * time_per_led, seconds)
            self.set_output_seconds('{}b'.format(i + 1), i * time_per_led, seconds)

    def marx_gen(self, pulse_length, dead_time, rep_rate):
        """
        10-stage solid state marx generator control with pulse signals on 'a' and charge signals on 'b'

        :param pulse_length:
        :param dead_time:
        :param rep_rate:
        :return:
        """

        self.set_io_init('1'*20)
        self.set_reprate_seconds(rep_rate)
        for i in range(0, NUM_CHANNELS):
            self.set_output_seconds('{}a'.format(i + 1), rep_rate-pulse_length, rep_rate)
            self.set_output_seconds('{}b'.format(i + 1), dead_time, rep_rate-dead_time)
