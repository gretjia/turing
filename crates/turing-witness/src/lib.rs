#![forbid(unsafe_code)]

use std::fs;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

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
    Io(std::io::Error),
    Jcs(JcsError),
    Json(serde_json::Error),
}

impl std::fmt::Display for WitnessError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WitnessError::Invalid(m) => write!(f, "witness invalid: {m}"),
            WitnessError::Append(e) => write!(f, "witness append error: {e}"),
            WitnessError::Git(e) => write!(f, "witness git error: {e}"),
            WitnessError::Io(e) => write!(f, "witness I/O error: {e}"),
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
            WitnessError::Io(e) => Some(e),
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
impl From<std::io::Error> for WitnessError {
    fn from(e: std::io::Error) -> Self {
        WitnessError::Io(e)
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

    pub fn to_v1_json(&self) -> Result<Value, WitnessError> {
        self.v1_payload()
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

    pub fn to_v1_json(&self) -> Result<Value, WitnessError> {
        self.to_v1_payload()
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TerminalKind {
    Halted,
    BudgetExhausted,
}

impl TerminalKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            TerminalKind::Halted => "HALTED",
            TerminalKind::BudgetExhausted => "BUDGET_EXHAUSTED",
        }
    }

    pub fn event_type(&self) -> &'static str {
        match self {
            TerminalKind::Halted => "ComputationHalted",
            TerminalKind::BudgetExhausted => "BudgetExhausted",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CertificateClass {
    C1StaticHaltUnreachable,
    C2StateRecurrence,
    C3BudgetBounded,
}

impl CertificateClass {
    pub fn as_str(&self) -> &'static str {
        match self {
            CertificateClass::C1StaticHaltUnreachable => "C1_STATIC_HALT_UNREACHABILITY",
            CertificateClass::C2StateRecurrence => "C2_STATE_RECURRENCE",
            CertificateClass::C3BudgetBounded => "C3_BUDGET_BOUNDED",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WitnessExecution {
    pub program_id: String,
    pub final_state: MachineState,
    pub final_state_hash: String,
    pub terminal_event_id: String,
    pub terminal_event_type: String,
    pub terminal_kind: TerminalKind,
    pub steps_executed: usize,
    pub events: Vec<WitnessEvent>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WitnessReduction {
    pub program_id: String,
    pub final_state: MachineState,
    pub final_state_hash: String,
    pub terminal_event_id: String,
    pub terminal_event_type: String,
    pub terminal_kind: TerminalKind,
    pub steps_executed: usize,
    pub events: Vec<WitnessEvent>,
}

#[derive(Debug, Clone)]
pub struct ProgramFixture {
    pub program_id: String,
    pub category: String,
    pub program: CounterMachineProgram,
    pub initial_state: MachineState,
    pub step_budget: usize,
    pub expected_terminal_kind: TerminalKind,
    pub certificate_class: Option<CertificateClass>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Tc3RunExport {
    pub program_id: String,
    pub expected_terminal_event: String,
    pub terminal_event_id: String,
    pub final_state_hash: String,
    pub steps_executed: usize,
    pub bundle_path: PathBuf,
    pub bundle_sha256: String,
    pub certificate_class: Option<CertificateClass>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Tc3ExportReport {
    pub root: PathBuf,
    pub program_count: usize,
    pub halting_program_count: usize,
    pub nonhalting_program_count: usize,
    pub runs: Vec<Tc3RunExport>,
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
    let execution = emit_witness_execution(
        repo,
        writer_id,
        program_id,
        program,
        initial_state,
        step_budget,
        None,
    )?;
    if execution.terminal_kind != TerminalKind::Halted {
        return Err(WitnessError::Invalid(format!(
            "run did not halt: terminal={}",
            execution.terminal_event_type
        )));
    }
    Ok(WitnessRun {
        program_id: execution.program_id,
        final_state: execution.final_state,
        final_state_hash: execution.final_state_hash,
        halted_event_id: execution.terminal_event_id,
        events: execution.events,
    })
}

pub fn emit_witness_execution(
    repo: &Path,
    writer_id: &str,
    program_id: &str,
    program: &CounterMachineProgram,
    initial_state: MachineState,
    step_budget: usize,
    budget_certificate: Option<Value>,
) -> Result<WitnessExecution, WitnessError> {
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
    if state.halted {
        let final_hash = state_hash_v1(&state)?;
        let receipt = tape.append(
            AppendRequest::new(
                "ComputationHalted",
                writer_id,
                json!({
                    "program_id": program_id,
                    "final_step_index": 0,
                    "final_state": state.v1_payload()?,
                    "final_state_hash": final_hash,
                    "halt_kind": "EXPLICIT_HALT",
                }),
            )
            .predicate_pass(),
        )?;
        let terminal_event_id = receipt.event_id.clone();
        record(&mut events, "ComputationHalted", receipt);
        return Ok(WitnessExecution {
            program_id: program_id.to_string(),
            final_state: state,
            final_state_hash: final_hash,
            terminal_event_id,
            terminal_event_type: "ComputationHalted".to_string(),
            terminal_kind: TerminalKind::Halted,
            steps_executed: 0,
            events,
        });
    }
    while !state.halted {
        if step_index >= step_budget {
            let final_hash = state_hash_v1(&state)?;
            let receipt = tape.append(
                AppendRequest::new(
                    "BudgetExhausted",
                    writer_id,
                    json!({
                        "program_id": program_id,
                        "steps_executed": step_index,
                        "step_budget": step_budget,
                        "last_state": state.v1_payload()?,
                        "last_state_hash": final_hash,
                        "certificate": budget_certificate.unwrap_or_else(|| json!({
                            "class": CertificateClass::C3BudgetBounded.as_str(),
                            "claim": "did_not_halt_within_recorded_step_budget",
                        })),
                    }),
                )
                .predicate_pass(),
            )?;
            let terminal_event_id = receipt.event_id.clone();
            record(&mut events, "BudgetExhausted", receipt);
            return Ok(WitnessExecution {
                program_id: program_id.to_string(),
                final_state: state,
                final_state_hash: final_hash,
                terminal_event_id,
                terminal_event_type: "BudgetExhausted".to_string(),
                terminal_kind: TerminalKind::BudgetExhausted,
                steps_executed: step_index,
                events,
            });
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
            let terminal_event_id = receipt.event_id.clone();
            record(&mut events, "ComputationHalted", receipt);
            return Ok(WitnessExecution {
                program_id: program_id.to_string(),
                final_state: state,
                final_state_hash: final_hash,
                terminal_event_id,
                terminal_event_type: "ComputationHalted".to_string(),
                terminal_kind: TerminalKind::Halted,
                steps_executed: step_index + 1,
                events,
            });
        }
        step_index += 1;
    }

    Err(WitnessError::Invalid(
        "execution exited without terminal event".to_string(),
    ))
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
    let mut terminal_event_id: Option<String> = None;
    let mut terminal_event_type: Option<String> = None;
    let mut terminal_kind: Option<TerminalKind> = None;
    let mut steps_executed: Option<usize> = None;
    let mut events = Vec::new();

    for event_id in walk_to_genesis(repo, tape_tip_event_id)? {
        let env = read_envelope(repo, &event_id)?;
        if !is_witness_event(&env.event_type) {
            continue;
        }
        if terminal_kind.is_some() {
            return Err(WitnessError::Invalid(format!(
                "witness event after terminal: {}",
                env.event_type
            )));
        }
        let head_moved = head_moved_from_body(&env.event_type)?;
        events.push(WitnessEvent {
            event_id: event_id.clone(),
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
                terminal_event_id = Some(event_id.clone());
                terminal_event_type = Some("ComputationHalted".to_string());
                terminal_kind = Some(TerminalKind::Halted);
                steps_executed = Some(value_usize(&env.payload, "final_step_index")? + 1);
            }
            "BudgetExhausted" => {
                ensure_program_id(&program_id, &env.payload)?;
                let exhausted = MachineState::from_v1_payload(field(&env.payload, "last_state")?)?;
                if exhausted.halted {
                    return Err(WitnessError::Invalid(
                        "BudgetExhausted last_state is halted".to_string(),
                    ));
                }
                let exhausted_hash = payload_str(&env.payload, "last_state_hash")?.to_string();
                ensure_eq(
                    &exhausted_hash,
                    &state_hash_v1(&exhausted)?,
                    "last_state_hash",
                )?;
                ensure_eq(
                    state.as_ref().unwrap_or(&exhausted),
                    &exhausted,
                    "budget final state",
                )?;
                let executed = value_usize(&env.payload, "steps_executed")?;
                ensure_eq(
                    &executed,
                    &value_usize(&env.payload, "step_budget")?,
                    "budget steps_executed",
                )?;
                final_state = Some(exhausted);
                final_state_hash = Some(exhausted_hash);
                terminal_event_id = Some(event_id.clone());
                terminal_event_type = Some("BudgetExhausted".to_string());
                terminal_kind = Some(TerminalKind::BudgetExhausted);
                steps_executed = Some(executed);
            }
            _ => {}
        }
    }
    if pending.is_some() {
        return Err(WitnessError::Invalid(
            "terminal reached with an unapplied pending state observation".to_string(),
        ));
    }

    Ok(WitnessReduction {
        program_id: program_id.ok_or_else(|| WitnessError::Invalid("no program id".to_string()))?,
        final_state: final_state
            .ok_or_else(|| WitnessError::Invalid("no witness terminal event".to_string()))?,
        final_state_hash: final_state_hash
            .ok_or_else(|| WitnessError::Invalid("no final state hash".to_string()))?,
        terminal_event_id: terminal_event_id
            .ok_or_else(|| WitnessError::Invalid("no terminal event id".to_string()))?,
        terminal_event_type: terminal_event_type
            .ok_or_else(|| WitnessError::Invalid("no terminal event type".to_string()))?,
        terminal_kind: terminal_kind
            .ok_or_else(|| WitnessError::Invalid("no terminal kind".to_string()))?,
        steps_executed: steps_executed
            .ok_or_else(|| WitnessError::Invalid("no terminal step count".to_string()))?,
        events,
    })
}

pub fn tc3_program_fixtures() -> Result<Vec<ProgramFixture>, WitnessError> {
    Ok(vec![
        ProgramFixture {
            program_id: "copy_a_to_b".to_string(),
            category: "HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 0,
                    zero_pc: 2,
                    nonzero_pc: 1,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![3, 0], false)?,
            step_budget: 16,
            expected_terminal_kind: TerminalKind::Halted,
            certificate_class: None,
        },
        ProgramFixture {
            program_id: "add_a_b".to_string(),
            category: "HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 0,
                    zero_pc: 2,
                    nonzero_pc: 1,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![4, 2], false)?,
            step_budget: 16,
            expected_terminal_kind: TerminalKind::Halted,
            certificate_class: None,
        },
        ProgramFixture {
            program_id: "multiply_small".to_string(),
            category: "HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 0,
                    zero_pc: 4,
                    nonzero_pc: 1,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 2,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 3,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![2, 0], false)?,
            step_budget: 16,
            expected_terminal_kind: TerminalKind::Halted,
            certificate_class: None,
        },
        ProgramFixture {
            program_id: "branch_zero_nonzero".to_string(),
            category: "HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 0,
                    zero_pc: 2,
                    nonzero_pc: 1,
                },
                Instruction::Inc {
                    counter: 1,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![2, 0], false)?,
            step_budget: 16,
            expected_terminal_kind: TerminalKind::Halted,
            certificate_class: None,
        },
        ProgramFixture {
            program_id: "known_halting_busy_loop_with_budget".to_string(),
            category: "HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 1,
                    zero_pc: 2,
                    nonzero_pc: 1,
                },
                Instruction::Inc {
                    counter: 0,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![0, 5], false)?,
            step_budget: 16,
            expected_terminal_kind: TerminalKind::Halted,
            certificate_class: None,
        },
        ProgramFixture {
            program_id: "spin_static_halt_unreachable".to_string(),
            category: "NON_HALTING".to_string(),
            program: CounterMachineProgram::new(vec![Instruction::Inc {
                counter: 0,
                next_pc: 0,
            }])?,
            initial_state: MachineState::new(0, vec![0, 0], false)?,
            step_budget: 8,
            expected_terminal_kind: TerminalKind::BudgetExhausted,
            certificate_class: Some(CertificateClass::C1StaticHaltUnreachable),
        },
        ProgramFixture {
            program_id: "recurs_zero_decjz".to_string(),
            category: "NON_HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 0,
                    zero_pc: 0,
                    nonzero_pc: 1,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![0, 0], false)?,
            step_budget: 8,
            expected_terminal_kind: TerminalKind::BudgetExhausted,
            certificate_class: Some(CertificateClass::C2StateRecurrence),
        },
        ProgramFixture {
            program_id: "guarded_growth_budget".to_string(),
            category: "NON_HALTING".to_string(),
            program: CounterMachineProgram::new(vec![
                Instruction::DecJz {
                    counter: 1,
                    zero_pc: 1,
                    nonzero_pc: 2,
                },
                Instruction::Inc {
                    counter: 0,
                    next_pc: 0,
                },
                Instruction::Halt,
            ])?,
            initial_state: MachineState::new(0, vec![0, 0], false)?,
            step_budget: 8,
            expected_terminal_kind: TerminalKind::BudgetExhausted,
            certificate_class: Some(CertificateClass::C3BudgetBounded),
        },
    ])
}

pub fn export_tc3_corpus(root: &Path) -> Result<Tc3ExportReport, WitnessError> {
    let root = absolute_path(root)?;
    let root = root.as_path();
    fs::create_dir_all(root)?;
    reset_generated_tc3_paths(root)?;
    fs::create_dir_all(root.join("programs").join("tc3"))?;
    fs::create_dir_all(root.join("tapes"))?;
    fs::create_dir_all(root.join("traces"))?;
    fs::create_dir_all(root.join("fuzz"))?;

    write_text(
        &root.join("README.md"),
        "# Turing Completeness Witness TC3 Evidence\n\nEvidence class: REAL_DETERMINISTIC_EXECUTION.\n\nThis root contains deterministic TC0-TC3 witness artifacts: frozen schemas, five halting runs, three budget-stopped non-halting examples with C1/C2/C3 certificates, git bundles for each tape, and a seed-pinned fuzz corpus. This evidence does not claim TC-10, external verification, or unqualified Turing-completeness.\n",
    )?;
    write_text(
        &root.join("THEORY.md"),
        "# Theory Boundary\n\nThe executable witness is a two-counter Minsky-style counter machine with INC, DECJZ, and HALT instructions. Non-halting evidence is taxonomy-bound: C1 is static HALT-unreachability, C2 is exact deterministic state recurrence, and C3 is only a budget-bounded observation. The C3 claim is limited to did-not-halt within the recorded step budget.\n",
    )?;
    write_json(
        &root.join("CLAIM_BOUNDARY.json"),
        &json!({
            "schema_id": "turingos.tc_witness_claim_boundary.v1",
            "scope": "M2.TC3 run/export evidence",
            "status_ceiling": "IMPLEMENTER_ADDRESSED",
            "evidence_class": "REAL_DETERMINISTIC_EXECUTION",
            "turing_completeness_claim_allowed": false,
            "tc10_external_artifact_exists": false,
            "claims_allowed": [
                "five halting witness programs executed through MicroTape",
                "three budget-stopped non-halting examples recorded with C1/C2/C3 certificates",
                "git bundles and sha256 digests recorded for TC3 witness tapes",
                "seed-pinned fuzz corpus generated"
            ],
            "claims_forbidden": [
                "TuringOS is Turing-complete",
                "TC-10 passed",
                "EXTERNALLY_VERIFIED",
                "CLOSED",
                "RELEASED",
                "RATIFIED",
                "SHIPPED",
                "M2_ENABLED"
            ],
            "not_run_is_fail": true
        }),
    )?;

    let fixtures = tc3_program_fixtures()?;
    let mut runs = Vec::new();
    for fixture in &fixtures {
        let run = export_fixture(root, fixture)?;
        runs.push(run);
    }
    write_fuzz_corpus(root, 20260702, 500, 32, 4096)?;

    let halting_program_count = fixtures
        .iter()
        .filter(|fixture| fixture.expected_terminal_kind == TerminalKind::Halted)
        .count();
    let nonhalting_program_count = fixtures.len() - halting_program_count;
    let manifest_runs = runs
        .iter()
        .map(|run| {
            json!({
                "program_id": run.program_id,
                "expected_terminal_event": run.expected_terminal_event,
                "terminal_event_id": run.terminal_event_id,
                "final_state_hash": run.final_state_hash,
                "steps_executed": run.steps_executed,
                "bundle_path": path_slash(&run.bundle_path),
                "bundle_sha256": run.bundle_sha256,
                "certificate_class": run.certificate_class.map(|c| c.as_str()),
            })
        })
        .collect::<Vec<_>>();
    write_json(
        &root.join("bundle_manifest.json"),
        &json!({
            "schema_id": "turingos.tc3.bundle_manifest.v1",
            "evidence_class": "REAL_DETERMINISTIC_EXECUTION",
            "generator": "turing-witness tc3_export v1",
            "generated_at_utc": "2026-07-03T00:00:00Z",
            "program_count": fixtures.len(),
            "halting_program_count": halting_program_count,
            "nonhalting_program_count": nonhalting_program_count,
            "runs": manifest_runs,
        }),
    )?;
    let mut sha_lines = runs
        .iter()
        .map(|run| format!("{}  {}", run.bundle_sha256, path_slash(&run.bundle_path)))
        .collect::<Vec<_>>();
    sha_lines.sort();
    write_text(
        &root.join("bundle_sha256s.txt"),
        &(sha_lines.join("\n") + "\n"),
    )?;

    Ok(Tc3ExportReport {
        root: root.to_path_buf(),
        program_count: fixtures.len(),
        halting_program_count,
        nonhalting_program_count,
        runs,
    })
}

fn export_fixture(root: &Path, fixture: &ProgramFixture) -> Result<Tc3RunExport, WitnessError> {
    let program_rel = PathBuf::from("programs")
        .join("tc3")
        .join(format!("{}.json", fixture.program_id));
    let trace_rel = PathBuf::from("traces").join(format!("{}.json", fixture.program_id));
    let tape_dir_rel = PathBuf::from("tapes").join(&fixture.program_id);
    let repo = root.join(&tape_dir_rel).join("repo");
    let bundle_rel = tape_dir_rel.join("micro_tape.bundle");
    let bundle_abs = root.join(&bundle_rel);
    fs::create_dir_all(&repo)?;
    turing_git_tape::git::init_sha256(&repo)?;
    append_genesis(&repo)?;

    let certificate = fixture_certificate(fixture)?;
    write_json(
        &root.join(&program_rel),
        &json!({
            "schema_id": "turingos.tc3.program_fixture.v1",
            "program_id": fixture.program_id,
            "category": fixture.category,
            "program": fixture.program.to_v1_payload()?,
            "initial_state": fixture.initial_state.v1_payload()?,
            "step_budget": fixture.step_budget,
            "expected_terminal_event": fixture.expected_terminal_kind.event_type(),
            "certificate_class": fixture.certificate_class.map(|c| c.as_str()),
            "certificate": certificate,
        }),
    )?;

    let execution = emit_witness_execution(
        &repo,
        "writer:tc3",
        &fixture.program_id,
        &fixture.program,
        fixture.initial_state.clone(),
        fixture.step_budget,
        Some(certificate.clone()),
    )?;
    if execution.terminal_kind != fixture.expected_terminal_kind {
        return Err(WitnessError::Invalid(format!(
            "{} terminal mismatch: observed {}, expected {}",
            fixture.program_id,
            execution.terminal_kind.as_str(),
            fixture.expected_terminal_kind.as_str()
        )));
    }
    let reduced = reduce_witness_tape(&repo, &execution.terminal_event_id)?;
    ensure_eq(
        &reduced.final_state_hash,
        &execution.final_state_hash,
        "export reducer final hash",
    )?;

    write_json(
        &root.join(&trace_rel),
        &json!({
            "schema_id": "turingos.tc3.witness_trace.v1",
            "program_id": fixture.program_id,
            "terminal_event_id": execution.terminal_event_id,
            "terminal_event_type": execution.terminal_event_type,
            "terminal_kind": execution.terminal_kind.as_str(),
            "steps_executed": execution.steps_executed,
            "final_state": execution.final_state.v1_payload()?,
            "final_state_hash": execution.final_state_hash,
            "events": execution.events.iter().map(|event| json!({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "head_moved": format!("{:?}", event.head_moved),
            })).collect::<Vec<_>>(),
            "reducer_checked": true,
        }),
    )?;
    export_git_bundle(&repo, &bundle_abs)?;
    let bundle_sha256 = sha256_file(&bundle_abs)?;
    fs::remove_dir_all(&repo)?;

    Ok(Tc3RunExport {
        program_id: fixture.program_id.clone(),
        expected_terminal_event: fixture.expected_terminal_kind.event_type().to_string(),
        terminal_event_id: execution.terminal_event_id,
        final_state_hash: execution.final_state_hash,
        steps_executed: execution.steps_executed,
        bundle_path: bundle_rel,
        bundle_sha256,
        certificate_class: fixture.certificate_class,
    })
}

fn append_genesis(repo: &Path) -> Result<(), WitnessError> {
    let tape = Append::open(repo)?;
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:tc3-genesis",
            json!({"constitution_digest": digest_bytes(b"tc3-witness-genesis")}),
        )
        .predicate_pass(),
    )?;
    Ok(())
}

fn fixture_certificate(fixture: &ProgramFixture) -> Result<Value, WitnessError> {
    match fixture.certificate_class {
        Some(CertificateClass::C1StaticHaltUnreachable) => {
            let (reachable_pcs, halt_pcs, halt_reachable) = halt_reachability(&fixture.program);
            Ok(json!({
                "class": CertificateClass::C1StaticHaltUnreachable.as_str(),
                "checker": "control_flow_reachability_v1",
                "reachable_pcs": reachable_pcs,
                "halt_pcs": halt_pcs,
                "halt_reachable": halt_reachable,
            }))
        }
        Some(CertificateClass::C2StateRecurrence) => {
            let recurrence = find_recurrence(&fixture.program, fixture.initial_state.clone(), 8)?
                .ok_or_else(|| {
                WitnessError::Invalid(format!("{} has no recurrence", fixture.program_id))
            })?;
            Ok(json!({
                "class": CertificateClass::C2StateRecurrence.as_str(),
                "checker": "deterministic_state_hash_recurrence_v1",
                "first_step_index": recurrence.0,
                "second_step_index": recurrence.1,
                "state_hash": recurrence.2,
                "state": recurrence.3.v1_payload()?,
            }))
        }
        Some(CertificateClass::C3BudgetBounded) => Ok(json!({
            "class": CertificateClass::C3BudgetBounded.as_str(),
            "checker": "budget_stop_observation_v1",
            "claim": "did_not_halt_within_recorded_step_budget",
            "step_budget": fixture.step_budget,
        })),
        None => Ok(Value::Null),
    }
}

fn halt_reachability(program: &CounterMachineProgram) -> (Vec<usize>, Vec<usize>, bool) {
    let mut seen = vec![false; program.instructions.len()];
    let mut stack = vec![0usize];
    while let Some(pc) = stack.pop() {
        if pc >= program.instructions.len() || seen[pc] {
            continue;
        }
        seen[pc] = true;
        match program.instructions[pc] {
            Instruction::Inc { next_pc, .. } => stack.push(next_pc),
            Instruction::DecJz {
                zero_pc,
                nonzero_pc,
                ..
            } => {
                stack.push(zero_pc);
                stack.push(nonzero_pc);
            }
            Instruction::Halt => {}
        }
    }
    let reachable_pcs = seen
        .iter()
        .enumerate()
        .filter_map(|(pc, reachable)| reachable.then_some(pc))
        .collect::<Vec<_>>();
    let halt_pcs = program
        .instructions
        .iter()
        .enumerate()
        .filter_map(|(pc, instruction)| matches!(instruction, Instruction::Halt).then_some(pc))
        .collect::<Vec<_>>();
    let halt_reachable = halt_pcs.iter().any(|pc| seen[*pc]);
    (reachable_pcs, halt_pcs, halt_reachable)
}

fn find_recurrence(
    program: &CounterMachineProgram,
    mut state: MachineState,
    max_steps: usize,
) -> Result<Option<(usize, usize, String, MachineState)>, WitnessError> {
    let mut seen = Vec::<(usize, String, MachineState)>::new();
    for step_index in 0..=max_steps {
        let hash = state_hash_v1(&state)?;
        if let Some((first_step, _, first_state)) =
            seen.iter().find(|(_, observed, _)| observed == &hash)
        {
            return Ok(Some((*first_step, step_index, hash, first_state.clone())));
        }
        seen.push((step_index, hash, state.clone()));
        if state.halted || step_index == max_steps {
            break;
        }
        state = program.step(&state)?.next_state;
    }
    Ok(None)
}

fn write_fuzz_corpus(
    root: &Path,
    seed: u64,
    program_count: usize,
    max_program_len: usize,
    max_steps: usize,
) -> Result<(), WitnessError> {
    let fuzz_dir = root.join("fuzz");
    write_json(
        &fuzz_dir.join("fuzz_manifest.json"),
        &json!({
            "schema_id": "turingos.tc3.fuzz_manifest.v1",
            "generator_version": "v1",
            "seed": seed,
            "program_count": program_count,
            "max_program_len": max_program_len,
            "max_steps": max_steps,
            "corpus": "fuzz/corpus.jsonl",
            "rust_results": "fuzz/rust_results.jsonl",
            "differential_results": "fuzz/differential_results.json",
        }),
    )?;
    let mut rng = Lcg::new(seed);
    let mut corpus = String::new();
    let mut results = String::new();
    for case_index in 0..program_count {
        let len = 1 + rng.usize(max_program_len);
        let mut instructions = Vec::new();
        for _ in 0..len {
            instructions.push(match rng.usize(3) {
                0 => Instruction::Inc {
                    counter: rng.usize(2),
                    next_pc: rng.usize(len),
                },
                1 => Instruction::DecJz {
                    counter: rng.usize(2),
                    zero_pc: rng.usize(len),
                    nonzero_pc: rng.usize(len),
                },
                _ => Instruction::Halt,
            });
        }
        let program = CounterMachineProgram::new(instructions)?;
        let initial_state = MachineState::new(0, vec![rng.u64_below(6), rng.u64_below(6)], false)?;
        let run = run_pure(&program, initial_state.clone(), max_steps)?;
        corpus.push_str(&serde_json::to_string(&json!({
            "case_id": format!("fuzz-{case_index:04}"),
            "program": program.to_v1_payload()?,
            "initial_state": initial_state.v1_payload()?,
            "max_steps": max_steps,
        }))?);
        corpus.push('\n');
        results.push_str(&serde_json::to_string(&json!({
            "case_id": format!("fuzz-{case_index:04}"),
            "terminal_kind": run.terminal_kind.as_str(),
            "steps_executed": run.steps_executed,
            "final_state": run.final_state.v1_payload()?,
            "final_state_hash": run.final_state_hash,
        }))?);
        results.push('\n');
    }
    write_text(&fuzz_dir.join("corpus.jsonl"), &corpus)?;
    write_text(&fuzz_dir.join("rust_results.jsonl"), &results)?;
    Ok(())
}

struct PureRun {
    terminal_kind: TerminalKind,
    steps_executed: usize,
    final_state: MachineState,
    final_state_hash: String,
}

fn run_pure(
    program: &CounterMachineProgram,
    mut state: MachineState,
    max_steps: usize,
) -> Result<PureRun, WitnessError> {
    for step_index in 0..max_steps {
        if state.halted {
            return Ok(PureRun {
                terminal_kind: TerminalKind::Halted,
                steps_executed: step_index,
                final_state_hash: state_hash_v1(&state)?,
                final_state: state,
            });
        }
        let trace = program.step(&state)?;
        state = trace.next_state;
        if state.halted {
            return Ok(PureRun {
                terminal_kind: TerminalKind::Halted,
                steps_executed: step_index + 1,
                final_state_hash: state_hash_v1(&state)?,
                final_state: state,
            });
        }
    }
    Ok(PureRun {
        terminal_kind: TerminalKind::BudgetExhausted,
        steps_executed: max_steps,
        final_state_hash: state_hash_v1(&state)?,
        final_state: state,
    })
}

struct Lcg {
    state: u64,
}

impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg { state: seed }
    }

    fn next(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn usize(&mut self, upper: usize) -> usize {
        (self.next() as usize) % upper
    }

    fn u64_below(&mut self, upper: u64) -> u64 {
        self.next() % upper
    }
}

fn reset_generated_tc3_paths(root: &Path) -> Result<(), WitnessError> {
    for path in [
        root.join("programs").join("tc3"),
        root.join("tapes"),
        root.join("traces"),
        root.join("fuzz"),
    ] {
        if path.exists() {
            fs::remove_dir_all(path)?;
        }
    }
    for path in [
        root.join("bundle_manifest.json"),
        root.join("bundle_sha256s.txt"),
        root.join("THEORY.md"),
        root.join("CLAIM_BOUNDARY.json"),
    ] {
        if path.exists() {
            fs::remove_file(path)?;
        }
    }
    Ok(())
}

fn absolute_path(path: &Path) -> Result<PathBuf, WitnessError> {
    if path.is_absolute() {
        Ok(path.to_path_buf())
    } else {
        Ok(std::env::current_dir()?.join(path))
    }
}

fn export_git_bundle(repo: &Path, bundle: &Path) -> Result<(), WitnessError> {
    if let Some(parent) = bundle.parent() {
        fs::create_dir_all(parent)?;
    }
    if bundle.exists() {
        fs::remove_file(bundle)?;
    }
    let output = git_command(repo, &["bundle", "create", bundle_path(bundle)?, "--all"])
        .stdin(Stdio::null())
        .output()?;
    if !output.status.success() {
        return Err(WitnessError::Invalid(format!(
            "git bundle create failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        )));
    }
    Ok(())
}

fn git_command(dir: &Path, args: &[&str]) -> Command {
    let mut cmd = Command::new("git");
    cmd.arg("-C").arg(dir);
    cmd.args(args);
    cmd.env("GIT_CONFIG_NOSYSTEM", "1");
    cmd.env("GIT_CONFIG_GLOBAL", "/dev/null");
    cmd.env("GIT_TERMINAL_PROMPT", "0");
    cmd
}

fn bundle_path(path: &Path) -> Result<&str, WitnessError> {
    path.to_str()
        .ok_or_else(|| WitnessError::Invalid(format!("non-UTF8 path: {path:?}")))
}

fn sha256_file(path: &Path) -> Result<String, WitnessError> {
    let bytes = fs::read(path)?;
    Ok(jcs::sha256_hex(&bytes))
}

fn write_json(path: &Path, value: &Value) -> Result<(), WitnessError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::File::create(path)?;
    file.write_all(serde_json::to_string_pretty(value)?.as_bytes())?;
    file.write_all(b"\n")?;
    Ok(())
}

fn write_text(path: &Path, text: &str) -> Result<(), WitnessError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, text)?;
    Ok(())
}

fn path_slash(path: &Path) -> String {
    path.components()
        .map(|component| component.as_os_str().to_string_lossy())
        .collect::<Vec<_>>()
        .join("/")
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
        | "ComputationHalted"
        | "BudgetExhausted" => HeadMoved::None,
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
            | "BudgetExhausted"
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
