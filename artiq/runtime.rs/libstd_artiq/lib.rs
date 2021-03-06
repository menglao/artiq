#![feature(lang_items, asm, alloc, collections, libc, needs_panic_runtime)]
#![no_std]
#![needs_panic_runtime]

extern crate alloc_artiq;
extern crate alloc;
extern crate collections;
extern crate libc;

pub use core::{any, cell, clone, cmp, convert, default, hash, iter, marker, mem, num,
    ops, option, ptr, result, sync,
    char, i16, i32, i64, i8, isize, u16, u32, u64, u8, usize, f32, f64};
pub use alloc::{arc, rc, oom, raw_vec};
pub use collections::{binary_heap, borrow, boxed, btree_map, btree_set, fmt, linked_list, slice,
    str, string, vec, vec_deque};

pub mod prelude {
    pub mod v1 {
        pub use core::prelude::v1::*;
        pub use collections::*;
    }
}

pub mod time;

use core::fmt::Write;

#[macro_export]
macro_rules! print {
    ($($arg:tt)*) => ($crate::print_fmt(format_args!($($arg)*)));
}

#[macro_export]
macro_rules! println {
    ($fmt:expr) => (print!(concat!($fmt, "\n")));
    ($fmt:expr, $($arg:tt)*) => (print!(concat!($fmt, "\n"), $($arg)*));
}

extern {
    fn putchar(c: libc::c_int) -> libc::c_int;
    fn readchar() -> libc::c_char;
}

pub struct Console;

impl core::fmt::Write for Console {
    fn write_str(&mut self, s: &str) -> Result<(), core::fmt::Error> {
        for c in s.bytes() { unsafe { putchar(c as i32); } }
        Ok(())
    }
}

pub fn print_fmt(args: self::core::fmt::Arguments) {
    let _ = Console.write_fmt(args);
}

#[lang = "panic_fmt"]
extern fn panic_fmt(args: self::core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    let _ = write!(Console, "panic at {}:{}: ", file, line);
    let _ = Console.write_fmt(args);
    let _ = write!(Console, "\nwaiting for debugger...\n");
    unsafe {
        let _ = readchar();
        loop { asm!("l.trap 0") }
    }
}

// Allow linking with crates that are built as -Cpanic=unwind even when the root crate
// is built with -Cpanic=abort.
#[allow(non_snake_case)]
#[no_mangle]
pub extern "C" fn _Unwind_Resume() -> ! {
    loop {}
}
