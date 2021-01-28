// Copyright 2020 Conflux Foundation. All rights reserved.
// Conflux is free software and distributed under GNU General Public License.
// See http://www.gnu.org/licenses/

use super::super::types::LocalizedBlockTrace;
use crate::rpc::traits::trace::Trace;
use cfx_addr::Network;
use cfx_types::H256;
use cfxcore::BlockDataManager;
use jsonrpc_core::{Error as RpcError, Result as JsonRpcResult};
use std::sync::Arc;

pub struct TraceHandler {
    data_man: Arc<BlockDataManager>,
    network: Network,
}

impl TraceHandler {
    pub fn new(data_man: Arc<BlockDataManager>, network: Network) -> Self {
        TraceHandler { data_man, network }
    }
}

impl Trace for TraceHandler {
    fn block_traces(
        &self, block_hash: H256,
    ) -> JsonRpcResult<Option<LocalizedBlockTrace>> {
        match self.data_man.block_traces_by_hash(&block_hash) {
            None => Ok(None),
            Some(t) => match LocalizedBlockTrace::from(t, self.network) {
                Ok(t) => Ok(Some(t)),
                Err(e) => Err(RpcError::invalid_params(format!(
                    "Traces not found for block {:?}: {:?}",
                    block_hash, e
                ))),
            },
        }
    }
}
