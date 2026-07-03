#![forbid(unsafe_code)]

use std::path::Path;

use serde_json::{Value, json};

use turing_contracts::envelope::MicroEventEnvelope;
use turing_contracts::jcs::{self, JcsError};
use turing_git_tape::append::{
    Append, AppendError, AppendRequest, CommittedReceipt, HeadMoved, commit_parents,
    committed_body_bytes,
};
use turing_git_tape::git::GitError;

const INSTRUCTION_REGISTRY_JSON: &str = include_str!(
    "../../../evidence/theory/turing_completeness_witness_20260703/programs/instruction_schema_registry.v1.json"
);
const PREDICATE_INSTRUCTION_ALLOWED: &str = "instruction_in_closed_table_and_budget_remaining";

#[derive(Debug)]
pub enum WitnessError {
    Invalid(String),
    Append(AppendError),
    Git(GitError),
    Jcs(JcsError),
    Json(serde_json::Error),
}

impl std::fmt::Display for WitnessError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WitnessError::Invalid(m) => write!(f, "witness invalid: {m}"),
            WitnessError::Append(e) => write!(f, "witness append error: {e}"),
            WitnessError::Git(e) => write!(f, "witness git error: {e}"),
            WitnessError::Jcs(e) => write!(f, "witness canonicalization error: {e}"),
            WitnessError::Json(e) => write!(f, "witness JSON error: {e}"),
        }
    }
}

impl std::error::Error for WitnessError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            WitnessError::Append(e) => Some(e),
            WitnessError::Git(e) => Some(e),
            WitnessError::Jcs(e) => Some(e),
            WitnessError::Json(e) => Some(e),
            WitnessError::Invalid(_) => None,
        }
    }
}

impl From<AppendError> for WitnessError {
    fn from(e: AppendError) -> Self {
        WitnessError::Append(e)
    }
}
impl From<GitError> for WitnessError {
    fn from(e: GitError) -> Self {
        WitnessError::Git(e)
    }
}
impl From<JcsError> for WitnessError {
    fn from(e: JcsError) -> Self {
        WitnessError::Jcs(e)
    }
}
impl From<serde_json::Error> for WitnessError {
    fn from(e: serde_json::Error) -> Self {
        WitnessError::Json(e)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Instruction {
    Inc {
        counter: usize,
        next_pc: usize,
    },
    DecJz {
        counter: usize,
        zero_pc: usize,
        nonzero_pc: usize,
    },
    Halt,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MachineState {
    pub program_counter: usize,
    pub counters: Vec<u64>,
    pub halted: bool,
}

impl MachineState {
    pub fn new(
        program_counter: usize,
        counters: Vec<u64>,
        halted: bool,
    ) -> Result<Self, WitnessError> {
        if counters.is_empty() {
            return Err(WitnessError::Invalid(
                "machine state must have at least one counter".to_string(),
            ));
        }
        Ok(MachineState {
            program_counter,
            counters,
            halted,
        })
    }

    fn v1_payload(&self) -> Result<Value, WitnessError> {
        if self.counters.len() != 2 {
            return Err(WitnessError::Invalid(format!(
                "v1 tape state requires exactly 2 counters, got {}",
                self.counters.len()
            )));
        }
        Ok(json!({
            "program_counter": self.program_counter,
            "counter_a": self.counters[0],
            "counter_b": self.counters[1],
            "halted": self.halted,
        }))
    }

    fn from_v1_payload(value: &Value) -> Result<Self, WitnessError> {
        let pc = value_usize(value, "program_counter")?;
        let counter_a = value_u64(value, "counter_a")?;
        let counter_b = value_u64(value, "counter_b")?;
        let halted = value
            .get("halted")
            .and_then(Value::as_bool)
            .ok_or_else(|| WitnessError::Invalid("state.halted must be bool".to_string()))?;
        MachineState::new(pc, vec![counter_a, counter_b], halted)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StepTrace {
    pub pc_before: usize,
    pub pc_after: usize,
    pub instruction: Instruction,
    pub prev_state: MachineState,
    pub next_state: MachineState,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CounterMachineProgram {
    instructions: Vec<Instruction>,
}

impl CounterMachineProgram {
    pub fn new(instructions: Vec<Instruction>) -> Result<Self, WitnessError> {
        if instructions.is_empty() {
            return Err(WitnessError::Invalid(
                "program must contain at least one instruction".to_string(),
            ));
        }
        let len = instructions.len();
        for instruction in &instructions {
            match instruction {
                Instruction::Inc { next_pc, .. } if *next_pc >= len => {
                    return Err(WitnessError::Invalid(format!(
                        "INC next_pc {next_pc} out of range"
                    )));
                }
                Instruction::DecJz {
                    zero_pc,
                    nonzero_pc,
                    ..
                } if *zero_pc >= len || *nonzero_pc >= len => {
                    return Err(WitnessError::Invalid(format!(
                        "DECJZ target out of range: zero_pc={zero_pc}, nonzero_pc={nonzero_pc}"
                    )));
                }
                _ => {}
            }
        }
        Ok(CounterMachineProgram { instructions })
    }

    pub fn step(&self, state: &MachineState) -> Result<StepTrace, WitnessError> {
        if state.halted {
            return Ok(StepTrace {
                pc_before: state.program_counter,
                pc_after: state.program_counter,
                instruction: Instruction::Halt,
                prev_state: state.clone(),
                next_state: state.clone(),
            });
        }
        let instruction = self
            .instructions
            .get(state.program_counter)
            .ok_or_else(|| {
                WitnessError::Invalid(format!(
                    "program counter {} out of range",
                    state.program_counter
                ))
            })?
            .clone();
        let pc_before = state.program_counter;
        let mut next = state.clone();
        match instruction {
            Instruction::Inc { counter, next_pc } => {
                let slot = next.counters.get_mut(counter).ok_or_else(|| {
                    WitnessError::Invalid(format!("counter {counter} out of range"))
                })?;
                *slot = slot
                    .checked_add(1)
                    .ok_or_else(|| WitnessError::Invalid("counter overflow".to_string()))?;
                next.program_counter = next_pc;
            }
            Instruction::DecJz {
                counter,
                zero_pc,
                nonzero_pc,
            } => {
                let slot = next.counters.get_mut(counter).ok_or_else(|| {
                    WitnessError::Invalid(format!("counter {counter} out of range"))
                })?;
                if *slot == 0 {
                    next.program_counter = zero_pc;
                } else {
                    *slot -= 1;
                    next.program_counter = nonzero_pc;
                }
            }
            Instruction::Halt => {
                next.halted = true;
            }
        }
        Ok(StepTrace {
            pc_before,
            pc_after: next.program_counter,
            instruction: self.instructions[pc_before].clone(),
            prev_state: state.clone(),
            next_state: next,
        })
    }

    fn instruction(&self, pc: usize) -> Result<&Instruction, WitnessError> {
        self.instructions
            .get(pc)
            .ok_or_else(|| WitnessError::Invalid(format!("program counter {pc} out of range")))
    }

    fn to_v1_payload(&self) -> Result<Value, WitnessError> {
        self.instructions
            .iter()
            .map(Instruction::to_v1_payload)
            .collect::<Result<Vec<_>, _>>()
            .map(Value::Array)
    }

    fn from_v1_payload(value: &Value) -> Result<Self, WitnessError> {
        let array = value
            .as_array()
            .ok_or_else(|| WitnessError::Invalid("program must be array".to_string()))?;
        let mut instructions = Vec::with_capacity(array.len());
        for item in array {
            instructions.push(Instruction::from_v1_payload(item)?);
        }
        CounterMachineProgram::new(instructions)
    }
}

impl Instruction {
    fn to_v1_payload(&self) -> Result<Value, WitnessError> {
        match self {
            Instruction::Inc { counter, next_pc } => Ok(json!({
                "op": "INC",
                "counter": counter_name_v1(*counter)?,
                "next_pc": next_pc,
            })),
            Instruction::DecJz {
                counter,
                zero_pc,
                nonzero_pc,
            } => Ok(json!({
                "op": "DECJZ",
                "counter": counter_name_v1(*counter)?,
                "zero_pc": zero_pc,
                "nonzero_pc": nonzero_pc,
            })),
            Instruction::Halt => Ok(json!({"op": "HALT"})),
        }
    }

    fn from_v1_payload(value: &Value) -> Result<Self, WitnessError> {
        let op = value
            .get("op")
            .and_then(Value::as_str)
            .ok_or_else(|| WitnessError::Invalid("instruction.op must be string".to_string()))?;
        match op {
            "INC" => Ok(Instruction::Inc {
                counter: counter_index_v1(value)?,
                next_pc: value_usize(value, "next_pc")?,
            }),
            "DECJZ" => Ok(Instruction::DecJz {
                counter: counter_index_v1(value)?,
                zero_pc: value_usize(value, "zero_pc")?,
                nonzero_pc: value_usize(value, "nonzero_pc")?,
            }),
            "HALT" => Ok(Instruction::Halt),
            other => Err(WitnessError::Invalid(format!("unknown op {other:?}"))),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WitnessEvent {
    pub event_id: String,
    pub event_type: String,
    pub head_moved: HeadMoved,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WitnessRun {
    pub program_id: String,
    pub final_state: MachineState,
    pub final_state_hash: String,
    pub halted_event_id: String,
    pub events: Vec<WitnessEvent>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WitnessReduction {
    pub program_id: String,
    pub final_state: MachineState,
    pub final_state_hash: String,
    pub events: Vec<WitnessEvent>,
}

pub fn state_hash_v1(state: &MachineState) -> Result<String, WitnessError> {
    let bytes = jcs::canonicalize(&state.v1_payload()?)?;
    Ok(format!("sha256:{}", jcs::sha256_hex(&bytes)))
}

pub fn emit_witness_run(
    repo: &Path,
    writer_id: &str,
    program_id: &str,
    program: &CounterMachineProgram,
    initial_state: MachineState,
    step_budget: usize,
) -> Result<WitnessRun, WitnessError> {
    let tape = Append::open(repo)?;
    let mut events = Vec::new();
    let program_payload = program.to_v1_payload()?;
    let program_digest = digest_value(&program_payload)?;
    let instruction_registry_digest = digest_bytes(INSTRUCTION_REGISTRY_JSON.as_bytes());
    let initial_hash = state_hash_v1(&initial_state)?;
    record(
        &mut events,
        "ComputationStarted",
        tape.append(
            AppendRequest::new(
                "ComputationStarted",
                writer_id,
                json!({
                    "program_id": program_id,
                    "program_digest": program_digest,
                    "program": program_payload,
                    "initial_state": initial_state.v1_payload()?,
                    "state_hash": initial_hash,
                    "step_budget": step_budget,
                    "instruction_registry_digest": instruction_registry_digest,
                }),
            )
            .predicate_pass(),
        )?,
    );

    let mut state = initial_state;
    let mut step_index = 0usize;
    let mut halted_event_id = None;
    while !state.halted {
        if step_index >= step_budget {
            return Err(WitnessError::Invalid("step budget exhausted".to_string()));
        }
        let instruction = program.instruction(state.program_counter)?.clone();
        let instruction_payload = instruction.to_v1_payload()?;
        record(
            &mut events,
            "InstructionAuthorized",
            tape.append(
                AppendRequest::new(
                    "InstructionAuthorized",
                    writer_id,
                    json!({
                        "program_id": program_id,
                        "step_index": step_index,
                        "pc": state.program_counter,
                        "instruction": instruction_payload,
                        "predicate": PREDICATE_INSTRUCTION_ALLOWED,
                        "budget_remaining": step_budget - step_index,
                    }),
                )
                .predicate_pass(),
            )?,
        );

        let trace = program.step(&state)?;
        let prev_hash = state_hash_v1(&trace.prev_state)?;
        let next_hash = state_hash_v1(&trace.next_state)?;
        record(
            &mut events,
            "InstructionApplied",
            tape.append(
                AppendRequest::new(
                    "InstructionApplied",
                    writer_id,
                    json!({
                        "program_id": program_id,
                        "step_index": step_index,
                        "pc_before": trace.pc_before,
                        "pc_after": trace.pc_after,
                        "instruction": trace.instruction.to_v1_payload()?,
                        "prev_state_hash": prev_hash,
                        "next_state_hash": next_hash,
                    }),
                )
                .predicate_pass(),
            )?,
        );

        state = trace.next_state;
        record(
            &mut events,
            "MachineStateObserved",
            tape.append(
                AppendRequest::new(
                    "MachineStateObserved",
                    writer_id,
                    json!({
                        "program_id": program_id,
                        "step_index": step_index,
                        "state": state.v1_payload()?,
                        "state_hash": next_hash,
                    }),
                )
                .predicate_pass(),
            )?,
        );

        if state.halted {
            let final_hash = state_hash_v1(&state)?;
            let receipt = tape.append(
                AppendRequest::new(
                    "ComputationHalted",
                    writer_id,
                    json!({
                        "program_id": program_id,
                        "final_step_index": step_index,
                        "final_state": state.v1_payload()?,
                        "final_state_hash": final_hash,
                        "halt_kind": "EXPLICIT_HALT",
                    }),
                )
                .predicate_pass(),
            )?;
            halted_event_id = Some(receipt.event_id.clone());
            record(&mut events, "ComputationHalted", receipt);
        }
        step_index += 1;
    }

    let final_state_hash = state_hash_v1(&state)?;
    Ok(WitnessRun {
        program_id: program_id.to_string(),
        final_state: state,
        final_state_hash,
        halted_event_id: halted_event_id
            .ok_or_else(|| WitnessError::Invalid("run did not halt".to_string()))?,
        events,
    })
}

pub fn reduce_witness_tape(
    repo: &Path,
    tape_tip_event_id: &str,
) -> Result<WitnessReduction, WitnessError> {
    let mut program_id: Option<String> = None;
    let mut program: Option<CounterMachineProgram> = None;
    let mut state: Option<MachineState> = None;
    let mut state_hash: Option<String> = None;
    let mut pending: Option<(MachineState, String)> = None;
    let mut final_state: Option<MachineState> = None;
    let mut final_state_hash: Option<String> = None;
    let mut events = Vec::new();

    for event_id in walk_to_genesis(repo, tape_tip_event_id)? {
        let env = read_envelope(repo, &event_id)?;
        if !is_witness_event(&env.event_type) {
            continue;
        }
        let head_moved = head_moved_from_body(&env.event_type)?;
        events.push(WitnessEvent {
            event_id,
            event_type: env.event_type.clone(),
            head_moved,
        });
        match env.event_type.as_str() {
            "ComputationStarted" => {
                let pid = payload_str(&env.payload, "program_id")?.to_string();
                program_id = Some(pid);
                program = Some(CounterMachineProgram::from_v1_payload(field(
                    &env.payload,
                    "program",
                )?)?);
                let initial = MachineState::from_v1_payload(field(&env.payload, "initial_state")?)?;
                let hash = payload_str(&env.payload, "state_hash")?.to_string();
                ensure_eq(&hash, &state_hash_v1(&initial)?, "initial state hash")?;
                state = Some(initial);
                state_hash = Some(hash);
            }
            "InstructionAuthorized" => {
                ensure_program_id(&program_id, &env.payload)?;
                let current = state.as_ref().ok_or_else(|| {
                    WitnessError::Invalid("InstructionAuthorized before state".to_string())
                })?;
                let pc = value_usize(&env.payload, "pc")?;
                ensure_eq(&pc, &current.program_counter, "authorized pc")?;
                let expected = program
                    .as_ref()
                    .ok_or_else(|| WitnessError::Invalid("program missing".to_string()))?
                    .instruction(pc)?
                    .to_v1_payload()?;
                ensure_eq(
                    field(&env.payload, "instruction")?,
                    &expected,
                    "authorized instruction",
                )?;
                ensure_eq(
                    payload_str(&env.payload, "predicate")?,
                    PREDICATE_INSTRUCTION_ALLOWED,
                    "authorization predicate",
                )?;
                if value_usize(&env.payload, "budget_remaining")? == 0 {
                    return Err(WitnessError::Invalid(
                        "authorized instruction with no remaining budget".to_string(),
                    ));
                }
            }
            "InstructionApplied" => {
                ensure_program_id(&program_id, &env.payload)?;
                let current = state.as_ref().ok_or_else(|| {
                    WitnessError::Invalid("InstructionApplied before state".to_string())
                })?;
                let current_hash = state_hash.as_ref().ok_or_else(|| {
                    WitnessError::Invalid("InstructionApplied before state hash".to_string())
                })?;
                ensure_eq(
                    payload_str(&env.payload, "prev_state_hash")?,
                    current_hash,
                    "prev_state_hash",
                )?;
                let trace = program
                    .as_ref()
                    .ok_or_else(|| WitnessError::Invalid("program missing".to_string()))?
                    .step(current)?;
                ensure_eq(
                    &value_usize(&env.payload, "pc_before")?,
                    &trace.pc_before,
                    "pc_before",
                )?;
                ensure_eq(
                    &value_usize(&env.payload, "pc_after")?,
                    &trace.pc_after,
                    "pc_after",
                )?;
                ensure_eq(
                    field(&env.payload, "instruction")?,
                    &trace.instruction.to_v1_payload()?,
                    "applied instruction",
                )?;
                let next_hash = state_hash_v1(&trace.next_state)?;
                ensure_eq(
                    payload_str(&env.payload, "next_state_hash")?,
                    &next_hash,
                    "next_state_hash",
                )?;
                pending = Some((trace.next_state, next_hash));
            }
            "MachineStateObserved" => {
                ensure_program_id(&program_id, &env.payload)?;
                let observed = MachineState::from_v1_payload(field(&env.payload, "state")?)?;
                let observed_hash = payload_str(&env.payload, "state_hash")?.to_string();
                ensure_eq(
                    &observed_hash,
                    &state_hash_v1(&observed)?,
                    "observed state hash",
                )?;
                if let Some((expected_state, expected_hash)) = pending.take() {
                    ensure_eq(&observed, &expected_state, "observed state")?;
                    ensure_eq(&observed_hash, &expected_hash, "observed hash")?;
                }
                state = Some(observed);
                state_hash = Some(observed_hash);
            }
            "ComputationHalted" => {
                ensure_program_id(&program_id, &env.payload)?;
                let halted = MachineState::from_v1_payload(field(&env.payload, "final_state")?)?;
                if !halted.halted {
                    return Err(WitnessError::Invalid(
                        "ComputationHalted final_state is not halted".to_string(),
                    ));
                }
                let halted_hash = payload_str(&env.payload, "final_state_hash")?.to_string();
                ensure_eq(&halted_hash, &state_hash_v1(&halted)?, "final_state_hash")?;
                ensure_eq(state.as_ref().unwrap_or(&halted), &halted, "final state")?;
                final_state = Some(halted);
                final_state_hash = Some(halted_hash);
            }
            _ => {}
        }
    }

    Ok(WitnessReduction {
        program_id: program_id.ok_or_else(|| WitnessError::Invalid("no program id".to_string()))?,
        final_state: final_state
            .ok_or_else(|| WitnessError::Invalid("no ComputationHalted event".to_string()))?,
        final_state_hash: final_state_hash
            .ok_or_else(|| WitnessError::Invalid("no final state hash".to_string()))?,
        events,
    })
}

fn record(events: &mut Vec<WitnessEvent>, event_type: &str, receipt: CommittedReceipt) {
    events.push(WitnessEvent {
        event_id: receipt.event_id,
        event_type: event_type.to_string(),
        head_moved: receipt.head_moved,
    });
}

fn digest_value(value: &Value) -> Result<String, WitnessError> {
    let bytes = jcs::canonicalize(value)?;
    Ok(format!("sha256:{}", jcs::sha256_hex(&bytes)))
}

fn digest_bytes(bytes: &[u8]) -> String {
    format!("sha256:{}", jcs::sha256_hex(bytes))
}

fn counter_name_v1(counter: usize) -> Result<&'static str, WitnessError> {
    match counter {
        0 => Ok("counter_a"),
        1 => Ok("counter_b"),
        _ => Err(WitnessError::Invalid(format!(
            "v1 tape instruction requires counter 0 or 1, got {counter}"
        ))),
    }
}

fn counter_index_v1(value: &Value) -> Result<usize, WitnessError> {
    match payload_str(value, "counter")? {
        "counter_a" => Ok(0),
        "counter_b" => Ok(1),
        other => Err(WitnessError::Invalid(format!("unknown counter {other:?}"))),
    }
}

fn walk_to_genesis(repo: &Path, tip: &str) -> Result<Vec<String>, WitnessError> {
    let mut chain = Vec::new();
    let mut cursor = normalize_id(tip);
    loop {
        let parents = commit_parents(repo, &cursor)?;
        chain.push(cursor.clone());
        match parents.as_slice() {
            [] => break,
            [parent] => cursor = normalize_id(parent),
            many => {
                return Err(WitnessError::Invalid(format!(
                    "merge commit in tape: {} parents",
                    many.len()
                )));
            }
        }
    }
    chain.reverse();
    Ok(chain)
}

fn read_envelope(repo: &Path, event_id: &str) -> Result<MicroEventEnvelope, WitnessError> {
    let bytes = committed_body_bytes(repo, event_id)?;
    let value: Value = serde_json::from_slice(&bytes)?;
    MicroEventEnvelope::from_jcs_value(&value).map_err(WitnessError::from)
}

fn head_moved_from_body(event_type: &str) -> Result<HeadMoved, WitnessError> {
    Ok(match event_type {
        "InstructionAuthorized" => HeadMoved::AuthorizationHead,
        "ComputationStarted"
        | "InstructionApplied"
        | "MachineStateObserved"
        | "ComputationHalted" => HeadMoved::None,
        other => {
            return Err(WitnessError::Invalid(format!(
                "not a TC witness event: {other}"
            )));
        }
    })
}

fn is_witness_event(event_type: &str) -> bool {
    matches!(
        event_type,
        "ComputationStarted"
            | "InstructionAuthorized"
            | "InstructionApplied"
            | "MachineStateObserved"
            | "ComputationHalted"
    )
}

fn ensure_program_id(program_id: &Option<String>, payload: &Value) -> Result<(), WitnessError> {
    let expected = program_id
        .as_ref()
        .ok_or_else(|| WitnessError::Invalid("program id missing".to_string()))?;
    ensure_eq(payload_str(payload, "program_id")?, expected, "program_id")
}

fn ensure_eq<T: std::fmt::Debug + PartialEq + ?Sized>(
    observed: &T,
    expected: &T,
    label: &str,
) -> Result<(), WitnessError> {
    if observed == expected {
        Ok(())
    } else {
        Err(WitnessError::Invalid(format!(
            "{label} mismatch: observed={observed:?}, expected={expected:?}"
        )))
    }
}

fn field<'a>(value: &'a Value, key: &str) -> Result<&'a Value, WitnessError> {
    value
        .get(key)
        .ok_or_else(|| WitnessError::Invalid(format!("missing field {key}")))
}

fn payload_str<'a>(value: &'a Value, key: &str) -> Result<&'a str, WitnessError> {
    field(value, key)?
        .as_str()
        .ok_or_else(|| WitnessError::Invalid(format!("{key} must be string")))
}

fn value_usize(value: &Value, key: &str) -> Result<usize, WitnessError> {
    let n = value_u64(value, key)?;
    usize::try_from(n).map_err(|_| WitnessError::Invalid(format!("{key} out of range")))
}

fn value_u64(value: &Value, key: &str) -> Result<u64, WitnessError> {
    field(value, key)?
        .as_u64()
        .ok_or_else(|| WitnessError::Invalid(format!("{key} must be nonnegative integer")))
}

fn normalize_id(id: &str) -> String {
    match id.split_once(':') {
        Some((_, tail)) => format!("mu:{tail}"),
        None => format!("mu:{id}"),
    }
}
