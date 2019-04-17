#!/bin/python3
from math import log2

from matplotlib import pyplot as plt
from pprint import pprint

try:
    from pynq import Overlay
except ImportError:
    print('Running without PYNQ!')
    pass

REG_MAX_COUNT = 41
REG_IO_INIT = 40
ADDR_OFFSET = 4
CLOCK_PERIOD = 8e-9
NUM_OUTPUT = 20  # number of used IO ports
NUM_CHANNELS = 10
DEAD_TIME_MIN = 100e-9


class JvoAxiioDriver:
    def __init__(self,
                 bitfile='/home/xilinx/pynq/overlays/jvo6-axiio/axiio1_19.bit',
                 axiinput='jvo_axiinput_0'):
        try:
            self.overlay = Overlay(bitfile)
            self.io = getattr(self.overlay, axiinput)
        except NameError:
            print('Running without PYNQ!')
            pass
        print('initialization complete!')
        self.rep_rate_cycles = -1

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

    def set_rep_rate_seconds(self, seconds: float):
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
        self.set_rep_rate_cycles(num_cycles)

    def set_rep_rate_cycles(self, num_cycles: int):
        """
        Set reprate as number of cycles
        :param num_cycles:
        :return:
        """
        if log2(num_cycles) > 32:
            max_reprate = (2 ** 32 - 1) * CLOCK_PERIOD
            raise Exception('Number too large, maximum length is {} seconds.'.format(max_reprate))
        self.rep_rate_cycles = num_cycles
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

    def check_output_cycles(self, start: int, stop: int, rep_rate_cycles: int = 0):
        """
        Check if a number of cycles for an output is a valid value

        :param start: num cycles start time
        :param stop: num cycles stop time
        :param rep_rate_cycles: num cycles in reprate
        :return:
        """
        if rep_rate_cycles <= 0:
            if self.rep_rate_cycles > 0:
                rep_rate_cycles = self.rep_rate_cycles
            else:
                raise Exception('Invalid rep rate!')
        if (stop > rep_rate_cycles and start > rep_rate_cycles) or (stop < 0 and start < 0):
            return False
        else:
            if start > rep_rate_cycles:
                raise Exception('Start number is larger than rep. rate. This is not possible.')
            if stop > rep_rate_cycles:
                raise Exception('Stop number is larger than rep. rate. This is not possible.')
            if stop < start:
                raise Exception('Stop number should be larger than start number.')
            if stop == start:
                raise Exception('Stop number should not be equal to start number.')
        return True

    def set_output_cycles(self, output: str, start: int, stop: int):
        """
        Set start and stop time of output by number of cycles

        :param output: number of output as str 1a, 1b, 2a etc.
        :param start: start of pulse in num cycles
        :param stop: stop of pulse in num cycles
        :return:
        """
        io_num = 4 * (int(output[:-1]) - 1)  # all but last char should be numeric
        io_offset = 2 if output[-1] == 'b' else 0
        if not self.check_output_cycles(start, stop):
            print('output {} is disabled'.format(output))
        self.write_reg(io_num + io_offset, start)
        self.write_reg(io_num + io_offset + 1, stop)

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

        self.set_rep_rate_seconds(seconds)
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
        self.set_rep_rate_seconds(seconds)
        time_per_led = seconds / NUM_CHANNELS
        for i in range(0, NUM_CHANNELS):
            self.set_output_seconds('{}a'.format(i + 1), i * time_per_led, seconds)
            self.set_output_seconds('{}b'.format(i + 1), i * time_per_led, seconds)

    def _make_marx(self, channels: list, dead_time: float, rep_rate: float):
        """

        :param channels: dict with channel configs {'channel': [start, dur]}
        :param dead_time: dead time between pulse and charge
        :param rep_rate: repetition rate of cycli.
        :return:
        """
        assert NUM_OUTPUT / 2 == NUM_CHANNELS, 'Each channel should have 2 outputs.'
        plot_list = []
        table_list = []
        channel_list = []
        io_init = [1] * NUM_OUTPUT  # initial value of all signals, first 10 are signals
        first = rep_rate
        min_width = rep_rate

        if len(channels) > NUM_CHANNELS:
            raise Exception('{} channels defined, where {} is max'.format(len(channels), NUM_CHANNELS))
        if len(channels) != NUM_CHANNELS:
            raise Exception('{} channels defined, but {} should be defined.'.format(len(channels), NUM_CHANNELS))

        # check values and find charge bounds
        rep_rate_cycles = round(rep_rate / CLOCK_PERIOD)
        if log2(rep_rate_cycles) >= 32:
            max_reprate = (2 ** 32 - 3) * CLOCK_PERIOD
            raise Exception('Number too large, maximum length is {} seconds.'.format(max_reprate))
        dead_time_cycles = round(dead_time / CLOCK_PERIOD)
        if dead_time < DEAD_TIME_MIN:
            raise Exception('Dead time {} is shorter than minimum of {}'.format(dead_time, DEAD_TIME_MIN))

        assert len(channels) == NUM_CHANNELS
        for i, output in enumerate(channels):
            if (output[0] <= rep_rate and output[1] <= rep_rate) or \
                    (output[0] < 0 and output[1] < 0):  # not disabled
                width = output[1] - output[0]
                if width < min_width:
                    min_width = width
                if min_width < CLOCK_PERIOD:
                    raise Exception('Min width of {} is smaller than clock period {} for channel {}'.format(min_width, CLOCK_PERIOD, i + 1))
                if output[0] < first:
                    first = output[0]
                if output[1] > rep_rate and output[0] < rep_rate:  # only if channel is not disabled.
                    raise Exception('Last value of channel {} is larger than rep_rate {}'.format(i + 1, rep_rate))
                if output[0] < rep_rate / 2:
                    raise Exception('First value of channel {} is before half cycle, this gives too little time to charge'.format(i + 1))
                if output[1] < output[0]:
                    raise Exception('Start cannot be after end time for channel {}'.format(i + 1))

                num_cycles_start = round(output[0] / CLOCK_PERIOD)
                num_cycles_stop = round(output[1] / CLOCK_PERIOD)
            else:  # disabled output
                num_cycles_start = rep_rate_cycles + 2  # disabled output has too high number
                num_cycles_stop = rep_rate_cycles + 2  # disabled output has too high number

            table_list.append(['Channel_{}a'.format(i + 1), num_cycles_start, num_cycles_stop])
            channel_list.append([num_cycles_start, num_cycles_stop])
            # plot is inverted from the output waveform, because HFBR inverts signal once.
            if not self.check_output_cycles(num_cycles_start, num_cycles_stop, rep_rate_cycles):
                io_init[i] = 1  # disabled output
                plot_list.append([[0, rep_rate_cycles], [not io_init[i], not io_init[i]]])
            else:
                plot_list.append([[0, output[0], output[1], rep_rate], [not io_init[i], not io_init[i], io_init[i], not io_init[i]]])

        # plot channels
        fig, axs = plt.subplots(len(plot_list) + 1, 1, sharex=True, sharey=True)
        for i, plot in enumerate(plot_list):
            axs[i].step(plot[0], plot[1], linewidth=2)
            axs[i].set_ylabel('{}a'.format(i + 1))

        # charge pulse
        first_cycles = round(first / CLOCK_PERIOD)
        charge_start = dead_time_cycles
        charge_stop = first_cycles - dead_time_cycles
        table_list.append(['Charge', charge_start, charge_stop])

        # plot charge.
        # io_init[NUM_CHANNELS] will be the first charge output.
        axs[len(plot_list)].step(
            [0, dead_time, first - dead_time, rep_rate],
            [not io_init[NUM_CHANNELS], not io_init[NUM_CHANNELS], io_init[NUM_CHANNELS], not io_init[NUM_CHANNELS]], linewidth=2)
        axs[len(plot_list)].set_ylabel('crg')
        # set plot
        plt.xlim([first - 2 * dead_time, rep_rate])

        pprint(table_list)
        # apply
        if hasattr(self, 'io'):  # if running with pynq
            io_init = ''.join([str(i) for i in io_init])  # convert to string
            # make sure all charge channels (second half) are init at zero.
            assert io_init[NUM_CHANNELS:NUM_OUTPUT] == '1' * NUM_CHANNELS, 'Charge init not correct!'
            # write init values to axi
            self.set_io_init(io_init)
            # write reprate to axi
            self.set_rep_rate_cycles(rep_rate_cycles)
            # write channel start/stop to axi.
            for i, channel in enumerate(channel_list):
                self.set_output_cycles('{}a'.format(i + 1), channel[0], channel[1])
                self.set_output_cycles('{}b'.format(i + 1), charge_start, charge_stop)
            print('Apply finished!')

    def marx_sync(self, pulse_length: float, dead_time: float, rep_rate: float):
        """
        10-stage solid state marx generator control with pulse signals on 'a' and charge signals on 'b'

        :param pulse_length:
        :param dead_time:
        :param rep_rate:
        :return:
        """
        channels = []
        for i in range(0, NUM_CHANNELS):
            channels.append([rep_rate - pulse_length, rep_rate])
        self._make_marx(channels, dead_time, rep_rate)

    def marx_delta(self, shortest_length: float, dead_time: float, rep_rate: float, num_channels: int = NUM_CHANNELS):
        """
        Make delta shaped wave

        :param shortest_length:
        :param dead_time:
        :param rep_rate:
        :param num_channels:
        :return:
        """
        channels = []
        change = shortest_length / 2
        for i in range(0, num_channels):
            j = num_channels - i
            start = rep_rate - change * (j-1) - shortest_length - 2*i*change
            stop = rep_rate - change * (j-1)
            print(i, j, start, stop)
            channels.append([start, stop])
        for i in range(num_channels, NUM_CHANNELS):
            channels.append([rep_rate * 2, rep_rate * 2])  # disable outputs
        self._make_marx(channels, dead_time, rep_rate)

    def marx_one(self, pulse_length: float, dead_time: float, rep_rate: float, channel: int):
        """

        :param pulse_length:
        :param dead_time:
        :param rep_rate:
        :param channel:
        :return:
        """
        assert 0 < channel < NUM_CHANNELS, 'Incorrect channel number!'
        channels = []
        start = rep_rate - pulse_length
        stop = rep_rate
        for i in range(1, NUM_CHANNELS + 1):
            if i == channel:
                channels.append([start, stop])  # enable
            else:
                channels.append([rep_rate + 1, rep_rate + 1])  # disable
        self._make_marx(channels, dead_time, rep_rate)
