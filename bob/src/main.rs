use duct::cmd;
use uuid::Uuid;
use std::io::prelude::*;
use std::io::BufReader;
use std::io::BufWriter;
use std::io::Error;
use std::time::Duration;
use std::thread;
use std::thread::JoinHandle;
use std::sync::mpsc::{channel, Sender, Receiver};

// TODO put these in a yaml file for easier deployment on new servers:
const DROPBOX_DIR: &str = r#"D:\DROPBOX"#;
const DROPBOX_LINK_DIR: &str = r#"\\OpR-Marc-RC2\Data\DROPBOX"#;
const BUILD_TARGET: &str = r#"W:\Volumes"#;
const PYTHON_ENV: &str = r#"C:\Python39\Scripts"#;
const RAW_DATA_DIR: &str = r#"\\OpR-Marc-Syn3\Data\RawData"#;

fn run_and_filter_output<F>(command: Vec<String>, mut process_line: F) -> Result<i32, Error> 
    where F: FnMut(String) -> () {
    let mut args = vec![String::from("/C")];
    for arg in command {
        args.push(arg);
    }
    let command = cmd("cmd.exe", args);
    let reader = command.stderr_to_stdout().reader()?;
    let lines = BufReader::new(&reader).lines();
    for line in lines {
        match line {
            Ok(line) => process_line(line),
            Err(err) => return {
                let err_str = format!("{}", err);
                if err_str.contains("exited with code") {
                    Ok(err_str.split(" ")
                                .collect::<Vec<&str>>()
                                .pop().unwrap()
                                .parse::<i32>().unwrap())
                } else {
                    Err(err)
                }
            },
        }
    } 
    Ok(0)
}

#[test]
fn test_run_and_filter_output() {
    match run_and_filter_output(vec!["@echo Hello, world!".to_string()], |s| assert_eq!("Hello, world!", s)) {
        Ok(code) => assert_eq!(0, code),
        Err(err) => panic!("error {}", err)
    };
    match run_and_filter_output(vec!["@echo Hello, world! 1>&2".to_string()], |s| assert_eq!("Hello, world! ", s)) {
        Ok(code) => assert_eq!(0, code),
        Err(err) => panic!("error {}", err)
    };
    match run_and_filter_output(vec!["exit /b 1".to_string()], |s| println!("{}", s)) {
        Ok(code) => assert_eq!(1, code),
        Err(err) => panic!("error {}", err)
    };
    match run_and_filter_output(vec!["@echo".to_string(), "Hey".to_string(), ">".to_string(), "file.txt".to_string()], |_| {}) {
        Ok(code) => assert_eq!(0, code),
        Err(err) => panic!("error {}", err)
    };
}

fn run_and_print_output(command: Vec<String>) -> Result<i32, Error> {
    run_and_filter_output(command, |output| {
        println!("{}", output);
    })
}

/* If greater flexibility is needed than run_chain_and_save_output, this might be worth bringing back
fn run_chain_and_filter_output<F>(commands:Vec<Vec<&str>>, process_line: F, command_on_error: Vec<&str>) -> Result<i32, Error>
    where F: Fn(String) -> () {

    for command in commands {
        match run_and_filter_output(&command, &process_line) {
            Ok(0) => continue,
            Ok(error_code) => {
                println!("Error code {} from {:?}", error_code, command);
                return run_and_print_output(command_on_error);
            },
            Err(err) => {
                println!("Error {} from {:?}", err, command);
                return run_and_print_output(command_on_error);
            },
        }
    }
    Ok(0)
}
*/

// TODO implement .bob fileformat for queues, that also include a command on error at the end & can be parsed to this
struct CommandChain {
    commands: Vec<Vec<String>>,
    command_on_error: Vec<String>,
}

fn run_chain_and_save_output(chain: CommandChain) -> Result<i32, Error> {
    let commands = chain.commands;
    let command_on_error = chain.command_on_error;
    for command in commands {
        // TODO uuids are confusing for this when they could be timestamps.
        let uuid = Uuid::new_v4();
        // TODO this requires first making the bob-output folder manually:
        let output_file = format!("bob-output/{}.txt", uuid);
        let file = File::create(output_file).unwrap();
        let mut buffer = BufWriter::new(file);
        buffer.write_all(format!("{:?}\n", command).as_bytes()).unwrap();
        buffer.flush().unwrap();
        println!("{} {:?}", uuid, command);
        let is_robocopy = command[0] == "robocopy";
        match run_and_filter_output(command.clone(), |line| {
            buffer.write_all(line.as_bytes()).unwrap();
            buffer.write_all(b"\r\n").unwrap();
            buffer.flush().unwrap();
        }) {
            Ok(0) => continue,
            Ok(error_code) if is_robocopy && (error_code == 1 || error_code == 3) => continue, // Robocopy returns 1 on success. yikes
            Ok(error_code) => {
                println!("Error code {} from {:?}", error_code, command);
                return run_and_print_output(command_on_error);
            },
            Err(err) => {
                println!("Error {} from {:?}", err, command);
                return run_and_print_output(command_on_error);
            },
        }
    }
    Ok(0)
}

fn run_on_interval_and_filter_output<F>(command: Vec<String>, process_line: F, seconds: u64, command_on_error: Vec<String>) -> Result<i32, Error>
    where F: Fn(String) -> () {
    
    loop {
        match run_and_filter_output(command.clone(), &process_line) {
            Ok(0) => (),
            Ok(error_code) => {
                println!("Error code {} from {:?}", error_code, command);
                return run_and_print_output(command_on_error);
            },
            Err(err) => {
                println!("Error {} from {:?}", err, command);
                return run_and_print_output(command_on_error);
            },
        }
        thread::sleep(Duration::from_secs(seconds));
    }
}

fn send_rc3_build_chain(section: String, is_rebuild: bool, sender: &Sender<CommandChain>) {
    let temp_volume_dir = format!(r#"{}\RC3{}"#, BUILD_TARGET, section);
    let mosaic_report_dest = format!(r#"{}\MosaicReports\{}\MosaicReport.html"#, DROPBOX_LINK_DIR, section);
    let queue_file_dest = format!(r#"{}\queue{}.txt"#, PYTHON_ENV, section);
    let source = if is_rebuild {
        format!(r#"{}\RC3\{}"#, RAW_DATA_DIR, section)
    } else {
        format!(r#"{}\TEMXCopy\{}"#, DROPBOX_DIR, section)
    };
    let mut commands = vec![
                vec![
                    "RC3Import".to_string(),
                    temp_volume_dir.clone(),
                    source,
                ],
                vec![
                    "RC3Build".to_string(),
                    temp_volume_dir.clone()
                ],
                // TODO check that a tileset was generated
                // Automatic build finished with code 0. Prepare a queue file for the next build step.
                vec![
                    "@echo".to_string(),
                    format!(r#"copy-section-links~W:\Volumes\RC3\TEM\VolumeData.xml~{}\TEM\VolumeData.xml~bob-output"#, temp_volume_dir),
                    ">".to_string(),
                    queue_file_dest.clone(),
                ],
                vec![
                    "@echo".to_string(),
                    format!(r#"robocopy~{}\TEM~W:\Volumes\RC3\TEM\~/MT:32~/LOG:RC3Robocopy.log~/MOVE~/nfl~/nc~/ns~/np~/E~/TEE~/R:3~/W:1~/REG~/DCOPY:DAT~/XO"#, temp_volume_dir),
                    ">>".to_string(),
                    queue_file_dest.clone(),
                ],
                // TODO the queue file could also delete itself after it finishes 
                // Move the automatic build's mosaicreport files to DROPBOX and send a link.
                // If the mosaicreport files aren't there, the chain will fail (as it should) because that's
                // a secondary indicator of build failure
                robocopy_move(
                    format!(r#"{}\MosaicReport"#, temp_volume_dir.clone()),
                    format!(r#"{}\MosaicReports\{}\MosaicReport\"#, DROPBOX_DIR, section)),
                vec![
                    "move".to_string(),
                    format!(r#"{}\MosaicReport.html"#, temp_volume_dir),
                    mosaic_report_dest.clone(),
                ],
                // TODO bob queue is no longer a console command, you type Queue: {file} into the CLI
                rito(format!("{} built automatically. Check {} and run `cd {} && bob queue {}` on Build1 if it looks good", section, mosaic_report_dest, PYTHON_ENV, queue_file_dest)),
            ];

        if !is_rebuild {
            commands.push(robocopy_move(
                    format!(r#"{}\TEMXCopy\{}"#, DROPBOX_DIR, section),
                    format!(r#"{}\RC3\{}\"#, RAW_DATA_DIR, section)));
            commands.push(rito(format!("{} copied to RawData", section)));
        }
    sender.send(
        CommandChain {
            commands: commands,
            command_on_error: rito(format!("automatic copy and build for {} failed", section))
        }).unwrap();
}

// TODO handle rebuild requests (don't make a volume folder, etc.)
fn send_core_build_chain(section: String, is_rebuild: bool, sender: &Sender<CommandChain>) {
    let volume_dir = format!(r#"{}\TEMXCopy\{}volume"#, DROPBOX_DIR, section);
    let build_target = format!(r#"{}\{}"#, BUILD_TARGET, section);
    let section_dir = format!(r#"{}\TEMXCopy\{}"#, DROPBOX_DIR, section);
    sender.send(
        CommandChain {
            commands: vec![
                // Put the section in a "volume" folder because TEMCoreBuildFast expects a volume, not a single section
                vec![
                    "mkdir".to_string(),
                    volume_dir.clone(),
                ],
                vec![
                    "move".to_string(),
                    section_dir,
                    volume_dir.clone(),
                ],
                vec![
                    "TEMCoreBuildFast".to_string(),
                    build_target,
                    volume_dir,
                ],
                rito(format!("{0} built automatically.", section)),
            ],
            command_on_error: rito(format!("automatic core build for {0} failed", section))
        }).unwrap();
}

// Source: https://stackoverflow.com/a/35820003
use std::{
    fs::File,
    path::Path,
};
fn lines_from_file(filename: impl AsRef<Path>) -> Vec<String> {
    let file = File::open(filename).expect("no such file");
    let buf = BufReader::new(file);
    buf.lines()
        .map(|l| l.expect("Could not parse line"))
        .collect()
}

fn spawn_tem_message_reader_thread(tem_name: &'static str, sender: Sender<String>) -> JoinHandle<()> {
    thread::spawn(move || {
        run_on_interval_and_filter_output(
            vec![format!(r#"type N:\{0}\message.txt && break>N:\{0}\message.txt"#, tem_name)],
            |output| {
                sender.send(format!("{}: {}", tem_name, output)).unwrap();
            }, 
            60,
            rito(format!("bob the builder {} thread failed", tem_name))).unwrap();
        }
    )
}

fn rito(message: String) -> Vec<String> {
    vec!["rito".to_string(), "--slack".to_string(), "tem-bot".to_string(), message]
}

fn rito_image(path: String) -> Vec<String> {
    vec!["rito".to_string(), "--slack_image".to_string(), "tem-bot".to_string(), path]
}

fn robocopy_move<'a>(source: String, dest: String) -> Vec<String> {
    vec![
        "robocopy".to_string(),
        source,
        dest,
        "/MT:32".to_string(),
        "/LOG:RC3Robocopy.log".to_string(),
        "/MOVE".to_string(),
        "/nfl".to_string(),
        "/nc".to_string(),
        "/ns".to_string(),
        "/np".to_string(),
        "/E".to_string(),
        "/TEE".to_string(),
        "/R:3".to_string(),
        "/W:1".to_string(),
        "/REG".to_string(),
        "/DCOPY:DAT".to_string(),
        "/XO".to_string(),
    ]
}

use rustyline::error::ReadlineError;
use rustyline::Editor;

// TODO cli thread should allow raw commands to be run
// TODO cli thread could allow serialization/suspension of chains to restart bob????
// TODO set up commandchain reading so that .cmd files are already valid (ignore rem, tokenize, etc)
fn spawn_cli_thread(sender: Sender<String>) -> JoinHandle<()> {
    thread::spawn(move || {
        let mut rl = Editor::<()>::new();
        if rl.load_history("history.txt").is_err() {
            println!("No previous history.");
        }
        loop {
            let readline = rl.readline(">> ");
            match readline {
                Ok(line) => {
                    rl.add_history_entry(line.as_str());
                    // Pretend it's from a scope called CLI so the command gets saved to processed messages:
                    sender.send(format!("CLI: {}", line)).unwrap();
                },
                Err(ReadlineError::Interrupted) => {
                    println!("CTRL-C");
                    break
                },
                Err(ReadlineError::Eof) => {
                    println!("CTRL-D");
                    break
                },
                Err(err) => {
                    println!("Error: {:?}", err);
                    break
                }
            }
        }
        rl.save_history("history.txt").unwrap();
    })
    // TODO raw command


}

fn spawn_worker_thread(receiver: Receiver<CommandChain>) -> JoinHandle<()> {
    thread::spawn(move || {
        loop {
            let next_chain = receiver.recv().unwrap();
            run_chain_and_save_output(next_chain).unwrap();
        }
    })
}

fn spawn_command_thread(receiver: Receiver<String>, sender: Sender<CommandChain>) -> JoinHandle<()> {
    thread::spawn(move || {
        loop {
            let next_command = receiver.recv().unwrap();
            println!("saving the Message output: {}", next_command);
            let mut tokens = next_command.split(": ");
            let tem_name = tokens.next().unwrap();
            run_and_print_output(vec![format!(r#"@echo {} >> N:\{}\processedMessage.txt"#, next_command, tem_name)]).unwrap();
            match tokens.next() {
                Some("Copied") => {
                    let section = tokens.next().unwrap().split(" ").next().unwrap();
                    // handle core builds with TEMCoreBuildFast
                    if section.starts_with("core") {
                        send_core_build_chain(section.to_string(), false, &sender);
                    }
                    // handle RC3 builds by importing and building, then copying to rawdata
                    else {
                        println!("{}", section);
                        // copy to rawdata, automatically build to its own section
                        // (but do this in another thread, so notifications still pipe to Slack for other messages)
                        send_rc3_build_chain(section.to_string(), false, &sender);
                    }
                },
                Some("Rebuild") => {
                    let section = tokens.next().unwrap().split(" ").next().unwrap();
                    // handle core builds with TEMCoreBuildFast
                    if section.starts_with("core") {
                        send_core_build_chain(section.to_string(), true, &sender);
                    }
                    // handle RC3 rebuilds by building FROM rawdata
                    else {
                        println!("rebuilding {}", section);
                        // copy to rawdata, automatically build to its own section
                        // (but do this in another thread, so notifications still pipe to Slack for other messages)
                        send_rc3_build_chain(section.to_string(), true, &sender);
                    }

                },
                // Send snapshots to #tem-bot as images
                Some("Snapshot") => {
                    let snapshot_name = tokens.next().unwrap();
                    let snapshot_path = format!(r#"{}\{}"#, DROPBOX_DIR, snapshot_name);
                    run_chain_and_save_output(
                        CommandChain {
                            commands: vec![
                                rito_image(snapshot_path),
                            ],

                            command_on_error: rito(format!("snapshot -> slack failed for {}", snapshot_name))
                        }).unwrap();
                },
                // When run with the `queue` subcommand, queue commands from a text file and save their outputs:
                Some("Queue") => {
                    println!("called as queue");
                    // TODO allow passing arguments to a queue
                    // TODO convert cmd files to queue.txt files
            
                    let queue_file = tokens.next().unwrap().split(" ").next().unwrap();
                    let queue = lines_from_file(queue_file);
                    // TODO tokenize queue files by passing the lines through a filter that just prints each arg on a line
                    let queue: Vec<Vec<String>> = queue.iter().map(|line| line.split("~").map(|token| token.trim().to_string()).collect()).collect();
                    // TODO The file has to tokenize command arguments like~this~"even though it's weird"
                    sender.send(CommandChain {
                        commands: queue, 
                        command_on_error: rito(format!("bob queue {} failed", queue_file))
                    }).unwrap();
                },
                // This case will be used even if there's no colon in the message
                Some(other_label) => {
                    println!("{}", other_label);
                    run_and_print_output(rito(next_command)).unwrap();
                },
                // This case should never be used
                None => ()
            }
        }
    })
}

fn main() {
    // Create a channel for all Bob commands to be sent safely to a command processor thread:
    let (command_sender, command_receiver) = channel();

    // Create a channel for all Bob jobs to be sent safely to a single worker thread as CommandChains:
    let (chain_sender, chain_receiver) = channel();

    spawn_command_thread(command_receiver, chain_sender);
    spawn_worker_thread(chain_receiver);    

    // Two threads simply monitor the notification text files from the TEMs,
    // and will send lines from them to the command processor thread
    spawn_tem_message_reader_thread("TEM1", command_sender.clone());
    spawn_tem_message_reader_thread("TEM2", command_sender.clone());

    // The CLI thread listens for manually entered CommandChains via queues or raw commands
    spawn_cli_thread(command_sender.clone()).join().unwrap();
}