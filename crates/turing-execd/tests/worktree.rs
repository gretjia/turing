use std::fs;
use std::process::Command;

use turing_execd::macro_worktree::MacroWorktreeManager;

#[test]
fn worktree_isolated_per_capsule() {
    let temp = tempfile::tempdir().expect("temp dir");
    let repo = temp.path().join("repo");
    fs::create_dir(&repo).expect("repo dir");
    git(&repo, &["init"]);
    fs::write(repo.join("README.md"), "# demo\n").expect("write readme");
    git(&repo, &["add", "README.md"]);
    git(
        &repo,
        &[
            "-c",
            "user.name=turingos",
            "-c",
            "user.email=tape@turingos.local",
            "commit",
            "-m",
            "init",
        ],
    );

    let manager = MacroWorktreeManager::new(&repo, repo.join(".turingos/worktrees"));
    let worktree = manager
        .create_for_capsule("wc_demo")
        .expect("create capsule worktree");

    assert_ne!(worktree.path, repo);
    assert!(worktree.path.ends_with(".turingos/worktrees/wc_demo"));
    assert_eq!(worktree.branch, "turingos/wc_demo");
    assert!(worktree.is_isolated_from(&repo));
    assert!(worktree.path.join("README.md").exists());

    fs::write(worktree.path.join("WORKER_TOUCH"), "worker only\n").expect("write in worktree");
    assert!(
        !repo.join("WORKER_TOUCH").exists(),
        "worker writes must not land in the main repo root"
    );
}

fn git(repo: &std::path::Path, args: &[&str]) {
    let output = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_TERMINAL_PROMPT", "0")
        .output()
        .expect("git command runs");
    assert!(
        output.status.success(),
        "git {args:?} failed with {}: {}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );
}
