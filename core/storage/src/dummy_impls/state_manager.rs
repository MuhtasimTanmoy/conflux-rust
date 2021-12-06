use super::{
    config::storage_manager::StorageConfiguration, state::State,
    state_index::StateIndex, state_trait::StateManagerTrait,
};
use crate::{KvdbRocksdb, Result, SnapshotInfo};
use amt_db::{amt_db::cached_pp, AmtDb};
use cfx_internal_common::{
    consensus_api::StateMaintenanceTrait, StateAvailabilityBoundary,
};
use cfx_storage_primitives::dummy::StateRootWithAuxInfo;
use kvdb_rocksdb::{CompactionProfile, Database, DatabaseConfig};
use malloc_size_of::{MallocSizeOf, MallocSizeOfOps};
use malloc_size_of_derive::MallocSizeOf as MallocSizeOfDerive;
use parking_lot::{Mutex, RwLock, RwLockReadGuard};
use primitives::{EpochId, MerkleHash};
use std::{path::Path, sync::Arc};

// #[derive(MallocSizeOfDerive)]
pub struct StateManager {
    snapshot_epoch_count: u32,
    // Not support history version yet
    amt_db: Arc<RwLock<AmtDb>>,
}

impl MallocSizeOf for StateManager {
    fn size_of(&self, ops: &mut MallocSizeOfOps) -> usize {
        return 0;
        todo!()
    }
}

fn open_backend(db_dir: &str) -> Arc<Database> {
    let mut db_config = DatabaseConfig::with_columns(3);

    db_config.memory_budget = Some(128);
    db_config.compaction = CompactionProfile::auto(Path::new(db_dir));
    db_config.disable_wal = false;

    let db = Database::open(&db_config, db_dir).unwrap();

    Arc::new(db)
}

impl StateManager {
    pub fn get_storage_manager(&self) -> &StateManager { &*self }

    pub fn new(conf: StorageConfiguration) -> Result<Self> {
        println!("Init config");
        let pp = cached_pp();
        let backend = open_backend(conf.path_storage_dir.to_str().unwrap());
        Ok(Self {
            snapshot_epoch_count: conf.snapshot_epoch_count,
            amt_db: Arc::new(RwLock::new(AmtDb::new(backend, pp, true))),
        })
    }

    pub fn get_snapshot_epoch_count(&self) -> u32 { self.snapshot_epoch_count }

    pub fn maintain_state_confirmed<ConsensusInner: StateMaintenanceTrait>(
        &self, consensus_inner: &ConsensusInner, stable_checkpoint_height: u64,
        era_epoch_count: u64, confirmed_height: u64,
        state_availability_boundary: &RwLock<StateAvailabilityBoundary>,
    ) -> Result<()>
    {
        warn!("StorageStateManager: No op for maintain_state_confirmed, stable_checkpoint_height {}, era_epoch_count {}, confirmed_height {}", stable_checkpoint_height,era_epoch_count,confirmed_height);
        Ok(())
    }

    pub fn get_snapshot_info_at_epoch(
        &self, snapshot_epoch_id: &EpochId,
    ) -> Option<SnapshotInfo> {
        todo!()
    }

    pub fn log_usage(&self) {}
}

impl StateManagerTrait for StateManager {
    fn get_state_no_commit(
        self: &Arc<Self>, epoch_id: StateIndex, try_open: bool,
    ) -> Result<Option<State>> {
        assert!(epoch_id.is_read_only());
        Ok(Some(self.new_state(true, Some(epoch_id.state_root))))
    }

    fn get_state_for_next_epoch(
        self: &Arc<Self>, parent_epoch_id: StateIndex,
    ) -> Result<Option<State>> {
        if let Some(height) = parent_epoch_id.height {
            info!("Make state for epoch {}", height);
            assert_eq!(height + 1, self.amt_db.read().current_epoch()?)
        }

        Ok(Some(
            if parent_epoch_id.is_read_only() {
                self.new_state(true, Some(parent_epoch_id.state_root))
            } else {
                self.new_state(false, None)
            },
        ))
    }

    fn get_state_for_genesis_write(self: &Arc<Self>) -> State {
        assert_eq!(0, self.amt_db.read().current_epoch().unwrap());
        self.new_state(false, None)
    }
}

impl StateManager {
    fn new_state(
        &self, read_only: bool, root_with_aux: Option<StateRootWithAuxInfo>,
    ) -> State {
        State {
            read_only,
            state: self.amt_db.clone(),
            root_with_aux,
        }
    }
}
