// Copyright (c) The Diem Core Contributors
// SPDX-License-Identifier: Apache-2.0

// Copyright 2021 Conflux Foundation. All rights reserved.
// Conflux is free software and distributed under GNU General Public License.
// See http://www.gnu.org/licenses/

use serde::{Deserialize, Serialize};
use std::fmt;

/// Request to get a EpochChangeProof from current_epoch to target_epoch
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct EpochRetrievalRequest {
    pub start_epoch: u64,
    pub end_epoch: u64,
}

impl fmt::Display for EpochRetrievalRequest {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "EpochRetrievalRequest: start_epoch {}, end_epoch {}",
            self.start_epoch, self.end_epoch
        )
    }
}
