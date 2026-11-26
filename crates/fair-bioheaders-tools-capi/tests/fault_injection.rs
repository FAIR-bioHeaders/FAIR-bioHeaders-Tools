// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! A panic inside the boundary becomes FH_E_INTERNAL and the process
//! continues (Tools#207 section 3). Built only with `fault-injection`.

#![cfg(feature = "fault-injection")]

use fhcore::*;
use std::ptr;

#[test]
fn panic_becomes_internal_and_process_survives() {
    let mut err = ptr::null_mut();
    assert_eq!(unsafe { fh_test_panic(&mut err) }, FH_E_INTERNAL);
    assert_eq!(unsafe { fh_error_code(err) }, FH_E_INTERNAL);
    let (mut p, mut n) = (ptr::null(), 0);
    unsafe { fh_error_message(err, &mut p, &mut n) };
    let text = String::from_utf8_lossy(unsafe { std::slice::from_raw_parts(p, n) }).into_owned();
    assert!(text.contains("fault-injection"), "{text}");
    unsafe { fh_error_free(err) };
    // Still usable afterwards.
    let mut e = ptr::null_mut();
    assert_eq!(
        unsafe { fh_engine_new(ptr::null(), &mut e, ptr::null_mut()) },
        FH_OK
    );
    unsafe { fh_engine_free(e) };
}
