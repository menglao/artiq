from artiq.language.core import kernel, now_mu
from artiq.coredevice.rtio import rtio_output


class SAWG:
    """Smart arbitrary waveform generator channel.

    :param channel: RTIO channel number of the first channel (amplitude).
        Frequency and Phase are assumed to be the subsequent channels.
    """
    kernel_invariants = {"amplitude_scale", "frequency_scale", "phase_scale",
                         "channel"}

    def __init__(self, dmgr, channel, parallelism=4, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        cordic_gain = 1.646760258057163  # Cordic(width=16, guard=None).gain
        width = 16
        self.amplitude_scale = (1 << width)/2/cordic_gain
        self.phase_scale = 1 << width
        self.frequency_scale = self.core.coarse_ref_period / parallelism

    @kernel
    def set_amplitude_mu(self, amplitude=0):
        """Set DDS amplitude (machine units).

        :param amplitude: DDS amplitude in machine units.
        """
        rtio_output(now_mu(), self.channel, 0, amplitude)

    @kernel
    def set_amplitude(self, amplitude=0):
        """Set DDS amplitude.

        :param amplitude: DDS amplitude relative to full-scale.
        """
        self.set_amplitude_mu(amplitude*self.amplitude_scale)

    @kernel
    def set_frequency_mu(self, frequency=0):
        """Set DDS frequency (machine units).

        :param frequency: DDS frequency in machine units.
        """
        rtio_output(now_mu(), self.channel + 1, 0, frequency)

    @kernel
    def set_frequency(self, frequency=0):
        """Set DDS frequency.

        :param frequency: DDS frequency in Hz.
        """
        self.set_frequency_mu(frequency*self.frequency_scale)

    @kernel
    def set_phase_mu(self, phase=0):
        """Set DDS phase (machine units).

        :param phase: DDS phase in machine units.
        """
        rtio_output(now_mu(), self.channel + 2, 0, phase)

    @kernel
    def set_phase(self, phase=0):
        """Set DDS phase.

        :param phase: DDS phase relative in turns.
        """
        self.set_phase_mu(phase*self.phase_scale)
