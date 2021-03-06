import os, sys

from pythonparser import diagnostic

from artiq import __artiq_dir__ as artiq_dir

from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *

from artiq.compiler.module import Module
from artiq.compiler.embedding import Stitcher
from artiq.compiler.targets import OR1KTarget

# Import for side effects (creating the exception classes).
from artiq.coredevice import exceptions


def _render_diagnostic(diagnostic, colored):
    def shorten_path(path):
        return path.replace(artiq_dir, "<artiq>")
    lines = [shorten_path(path) for path in diagnostic.render(colored=colored)]
    return "\n".join(lines)

colors_supported = os.name == "posix"
class _DiagnosticEngine(diagnostic.Engine):
    def render_diagnostic(self, diagnostic):
        sys.stderr.write(_render_diagnostic(diagnostic, colored=colors_supported) + "\n")

class CompileError(Exception):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic

    def __str__(self):
        # Prepend a newline so that the message shows up on after
        # exception class name printed by Python.
        return "\n" + _render_diagnostic(self.diagnostic, colored=colors_supported)


@syscall
def rtio_init() -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nounwind", "nowrite"})
def rtio_get_counter() -> TInt64:
    raise NotImplementedError("syscall not simulated")


class Core:
    """Core device driver.

    :param ref_period: period of the reference clock for the RTIO subsystem.
        On platforms that use clock multiplication and SERDES-based PHYs,
        this is the period after multiplication. For example, with a RTIO core
        clocked at 125MHz and a SERDES multiplication factor of 8, the
        reference period is 1ns.
        The time machine unit is equal to this period.
    :param external_clock: whether the core device should switch to its
        external RTIO clock input instead of using its internal oscillator.
    :param ref_multiplier: ratio between the RTIO fine timestamp frequency
        and the RTIO coarse timestamp frequency (e.g. SERDES multiplication
        factor).
    :param comm_device: name of the device used for communications.
    """

    kernel_invariants = {
        "core", "ref_period", "coarse_ref_period", "ref_multiplier",
        "external_clock",
    }

    def __init__(self, dmgr, ref_period, external_clock=False,
                 ref_multiplier=8, comm_device="comm"):
        self.ref_period = ref_period
        self.external_clock = external_clock
        self.ref_multiplier = ref_multiplier
        self.coarse_ref_period = ref_period*ref_multiplier
        self.comm = dmgr.get(comm_device)

        self.first_run = True
        self.dmgr = dmgr
        self.core = self
        self.comm.core = self

    def compile(self, function, args, kwargs, set_result=None, with_attr_writeback=True):
        try:
            engine = _DiagnosticEngine(all_errors_are_fatal=True)

            stitcher = Stitcher(engine=engine, core=self, dmgr=self.dmgr)
            stitcher.stitch_call(function, args, kwargs, set_result)
            stitcher.finalize()

            module = Module(stitcher, ref_period=self.ref_period)
            target = OR1KTarget()

            library = target.compile_and_link([module])
            stripped_library = target.strip(library)

            return stitcher.embedding_map, stripped_library, \
                   lambda addresses: target.symbolize(library, addresses), \
                   lambda symbols: target.demangle(symbols)
        except diagnostic.Error as error:
            raise CompileError(error.diagnostic) from error

    def run(self, function, args, kwargs):
        result = None
        def set_result(new_result):
            nonlocal result
            result = new_result

        embedding_map, kernel_library, symbolizer, demangler = \
            self.compile(function, args, kwargs, set_result)

        if self.first_run:
            self.comm.check_ident()
            self.comm.switch_clock(self.external_clock)
            self.first_run = False

        self.comm.load(kernel_library)
        self.comm.run()
        self.comm.serve(embedding_map, symbolizer, demangler)

        return result

    @kernel
    def get_rtio_counter_mu(self):
        return rtio_get_counter()

    @kernel
    def reset(self):
        """Clear RTIO FIFOs, release RTIO PHY reset, and set the time cursor
        at the current value of the hardware RTIO counter plus a margin of
        125000 machine units."""
        rtio_init()
        at_mu(rtio_get_counter() + 125000)

    @kernel
    def break_realtime(self):
        """Set the time cursor after the current value of the hardware RTIO
        counter plus a margin of 125000 machine units.

        If the time cursor is already after that position, this function
        does nothing."""
        min_now = rtio_get_counter() + 125000
        if now_mu() < min_now:
            at_mu(min_now)
