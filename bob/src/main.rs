use std::thread;
use std::thread::JoinHandle;
use std::sync::mpsc::{channel, Sender, Receiver};
use std::convert::TryInto;
use threadpool::ThreadPool;
use std::fs;
use std::io::prelude::*;
use std::io::BufReader;
use std::collections::HashMap;

mod config;
use config::*;

mod run;
use run::*;

mod rito;
use rito::*;

mod robocopy;
use robocopy::*;

fn rc3_build_chain(section: String, is_rebuild: bool) -> CommandChain {
    let config = config_from_yaml();
    let temp_volume_dir = format!(r#"{}\RC3{}"#, config.build_target, section);
    let mosaic_report_dest = format!(r#"{}\MosaicReports\{}\MosaicReport.html"#, config.dropbox_link_dir, section);
    let source = if is_rebuild {
        format!(r#"{}\RC3\{}"#, config.raw_data_dir, section)
    } else {
        format!(r#"{}\TEMXCopy\{}"#, config.dropbox_dir, section)
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
        // Automatic build finished with code 0. 

        // TODO check that a tileset was generated.
        // TODO sent the mosaicreport overview to slack

        // Copy the automatic build's mosaicreport files to DROPBOX and send a link.
        // If the mosaicreport files aren't there, the chain will fail (as it should) because that's
        // a secondary indicator of build failure
        robocopy_copy(
            format!(r#"{}\MosaicReport"#, temp_volume_dir.clone()),
            format!(r#"{}\MosaicReports\{}\MosaicReport\"#, config.dropbox_dir, section)),
        vec![
            "copy".to_string(),
            format!(r#"{}\MosaicReport.html"#, temp_volume_dir),
            mosaic_report_dest.clone(),
        ],
        rito(format!("{0} built automatically. Check {1} and run `Merge: {0}` if it looks good", section, mosaic_report_dest)),
    ];

    if !is_rebuild {
        commands.push(robocopy_move(
                format!(r#"{}\TEMXCopy\{}"#, config.dropbox_dir, section),
                format!(r#"{}\RC3\{}\"#, config.raw_data_dir, section)));
        commands.push(rito(format!("{} copied to RawData", section)));
    }

    CommandChain {
        commands: commands,
        label: format!("automatic copy and build for RC3 {}", section)
    }
}

// TODO not all merges will be RC3 merges forever
fn send_rc3_merge_chain(section: String, sender: &Sender<CommandChain>) {
    let config = config_from_yaml();

    let temp_volume_dir = format!(r#"{}\RC3{}"#, config.build_target, section);

    sender.send(
        CommandChain {
            commands: vec![
                vec![    
                    "copy-section-links".to_string(),
                    r#"W:\Volumes\RC3\TEM\VolumeData.xml"#.to_string(), // TODO this is RC3 hard-coded
                    format!(r#"{}\TEM\VolumeData.xml"#, temp_volume_dir),
                    "bob-output".to_string()
                ],
                robocopy_move(
                    format!(r#"{}\TEM"#, temp_volume_dir),
                    r#"W:\Volumes\RC3\TEM\"#.to_string()),
                // Delete the temp volume
                vec![
                    "rmdir".to_string(),
                    "/S".to_string(),
                    "/Q".to_string(),
                    temp_volume_dir
                ],
            ],
            label: format!("automatic merge for {} into RC3", section)
        }).unwrap();
}

fn core_build_chain(section: String, is_rebuild: bool) -> CommandChain {
    let config = config_from_yaml();

    let section_dir = format!(r#"{}\TEMXCopy\{}"#, config.dropbox_dir, section);
    let section_parts = section.split("_").collect::<Vec<&str>>();

    match &section_parts[..] {
        ["core", volume, section_number] => {
            let volume_dir = format!(r#"{}\TEMXCopy\{}"#, config.dropbox_dir, volume.clone());
            let mosaic_report_dest = format!(r#"{}\MosaicReports\{}\MosaicReport.html"#, config.dropbox_link_dir, volume.clone());
            let build_target = format!(r#"{}\{}"#, config.build_target, volume.clone());

            // If the volume dir doesn't exist, make it
            fs::create_dir_all(&volume_dir).unwrap();

            let mut commands = vec![
                // Run TEMCoreBuildFast
                vec![
                    "TEMCoreBuildFast".to_string(),
                    build_target.clone(),
                    volume_dir.clone(),
                ],

                // Copy the automatic build's mosaicreport files to DROPBOX and send a link.
                // If the mosaicreport files aren't there, the chain will fail (as it should) because that's
                // a secondary indicator of build failure
                robocopy_copy(
                    format!(r#"{}\MosaicReport"#, build_target.clone()),
                    format!(r#"{}\MosaicReports\{}\MosaicReport\"#, config.dropbox_dir, volume.clone())),
                vec![
                    "copy".to_string(),
                    format!(r#"{}\MosaicReport.html"#, build_target.clone()),
                    mosaic_report_dest.clone(),
                ],
                rito(format!("{0} built automatically. Check {1}, and if all sections have been built properly, run `Deploy: {0}` if it looks good", volume, mosaic_report_dest)),
            ];

            // Unless this a rebuild attempt, sections need to be moved to their volume directory:
            if !is_rebuild {
                // Move section into volume dir
                commands.insert(0, vec![
                    "move".to_string(),
                    section_dir,
                    format!(r#"{}\{}"#, volume_dir.clone(), section_number.clone()),
                ]);
            }

            CommandChain {
                commands: commands,
                label: format!("automatic core build for {0}", section)
            }
        },
        _ => {
            run_and_print_output(rito(format!("{0} should be named with pattern core_[volume]_[section] and was not built automatically", section))).unwrap();
            // TODO this is an error, shouldn't be an empty chain
            CommandChain {
                commands: Vec::new(),
                label: "do nothing".to_string()
            }
        },
    }
    
}

fn send_core_fixmosaic_stage(volume:String, sections: Vec<String>, sender: &Sender<CommandChain>) {
    let config = config_from_yaml();

    let mosaic_report_dest = format!(r#"{}\MosaicReports\{}\MosaicReport.html"#, config.dropbox_link_dir, volume.clone());
    let build_target = format!(r#"{}\{}"#, config.build_target, volume.clone());

    let mut commands = vec![];

    // Delete existing mosaics
    for section in &sections {
        let section_folder = format!("{:04}", section.parse::<i32>().unwrap()); // "420" -> "0420", "13345" -> "13345"
        commands.push(vec![
            "del".to_string(),
            format!(r#"{}\TEM\{}\TEM\Grid_Cel128_Mes8_Mes8_Thr0.25_it10_sp4.mosaic"#, build_target, section_folder),
        ]);
    }

    commands.append(&mut vec![
        vec![
            "TEMCoreBuildFixMosaic_Stage".to_string(),
            build_target.clone(),
            sections.join(","),
        ],
        // Copy the automatic build's mosaicreport files to DROPBOX and send a link.
        // If the mosaicreport files aren't there, the chain will fail (as it should) because that's
        // a secondary indicator of build failure
        robocopy_copy(
            format!(r#"{}\MosaicReport"#, build_target.clone()),
            format!(r#"{}\MosaicReports\{}\MosaicReport\"#, config.dropbox_dir, volume.clone())),
        vec![
            "copy".to_string(),
            format!(r#"{}\MosaicReport.html"#, build_target.clone()),
            mosaic_report_dest.clone(),
        ],
        rito(format!("{0} mosaic fixed with stage positions automatically. Check {1}, and if all sections have been built properly, run `Deploy: {0}` if it looks good", volume, mosaic_report_dest)),
    ]);

    sender.send(
        CommandChain {
            commands: commands,
            label: format!("automatic fixmosaic_stage for {} {:?}", volume, sections)
        }).unwrap();
}

fn send_core_deploy_chain(volume: String, sender: &Sender<CommandChain>) {
    let config = config_from_yaml();

    let volume_dir = format!(r#"{}\{}"#, config.build_target.clone(), volume.clone());
    let deploy_dir = format!(r#"{}\{}"#, config.core_deployment_dir.clone(), volume.clone());

    sender.send(
        CommandChain {
            commands: vec![
                robocopy_copy(
                    volume_dir.clone(),
                    format!(r#"{}\"#,deploy_dir.clone())),
                vec![
                    "TEMCoreBuildOptimizeTiles".to_string(),
                    deploy_dir.clone(),
                ],
                vec![
                    "add-volume-path".to_string(),
                    format!(r#"{}\Mosaic.VikingXML"#, deploy_dir.clone()),
                    "bob-output".to_string() // backup dir for Mosaic.VikingXML files
                ],
                rito(format!(r#"{0} might be ready! Check http://storage1.connectomes.utah.edu/{0}/Mosaic.VikingXML in Viking"#, volume))
            ],
            label: format!("automatic core volume deployment for {0} to http://storage1.connectomes.utah.edu/{0}/Mosaic.VikingXML", volume)
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
    let config = config_from_yaml();
    thread::spawn(move || {
        run_on_interval_and_filter_output(
            vec![format!(r#"type {0}\{1}\message.txt && break>{0}\{1}\message.txt"#, config.notification_dir, tem_name)],
            |output| {
                sender.send(format!("{}: {}", tem_name, output)).unwrap();
            }, 
            60,
            rito(format!("bob the builder {} thread failed", tem_name))).unwrap();
        }
    )
}

use rustyline::error::ReadlineError;
use rustyline::Editor;

// TODO cli thread could allow serialization/suspension of chains to restart bob????
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
            rl.save_history("history.txt").unwrap();
        }
    })

}

fn spawn_worker_threadpool(receiver: Receiver<CommandChain>) -> JoinHandle<()> {
    let config = config_from_yaml();
    let pool = ThreadPool::new(config.worker_threads.try_into().unwrap());
    thread::spawn(move || {
        loop {
            let next_chain = receiver.recv().unwrap();
            pool.execute(move || {
                run_chain_and_save_output(next_chain).unwrap();
            });
        }
    })
}

fn build_chain(section:&str, is_rebuild: bool) -> CommandChain {
    if section.starts_with("core") {
        core_build_chain(section.to_string(), is_rebuild)
    }
    else {
        println!("{}", section);
        rc3_build_chain(section.to_string(), is_rebuild)
    }
}

enum CommandBehavior {
    Immediate(CommandChain),
    Queue(CommandChain),
    NoOp,
}
use crate::CommandBehavior::*;

fn spawn_command_thread(receiver: Receiver<String>, sender: Sender<CommandChain>) -> JoinHandle<()> {
 
    // TODO make commands return result<CommandBehavior>
    let mut commands:HashMap<String, fn(Vec<String>) -> Option<CommandBehavior>> = HashMap::new();
    commands.insert("Copied".to_string(), |args|
        match args.as_slice() {
            [capture_dir] => {
                let config = config_from_yaml();
                Some(if config.automatic_builds {
                        Queue(build_chain(capture_dir, false))
                    } else { NoOp })
            },
            _ => None
        }
    );
    
    thread::spawn(move || {
        loop {
            let next_command_full = receiver.recv().unwrap();
            println!("saving the Message output: {}", next_command_full);
            let mut command_parts = next_command_full.split(": ");
            let tem_name = command_parts.next().unwrap();
            let command_name = command_parts.next().unwrap();
            let command_args = command_parts.next().unwrap().split(" ").map(|s| s.to_string()).collect::<Vec<String>>();
            let config = config_from_yaml();
            run_and_print_output(vec![format!(r#"@echo {} >> {}\{}\processedMessage.txt"#, config.notification_dir, next_command_full, tem_name)]).unwrap();

            let command_behavior = commands.get(command_name).unwrap();

            match command_behavior(command_args) {
                // TODO won't be matching Some, will be matchking Ok()
                Some(Immediate(chain)) => {
                    run_chain_and_save_output(chain).unwrap();
                },
                Some(Queue(chain)) => {
                    sender.send(chain).unwrap();
                },
                Some(NoOp) => {},
                None => { run_and_print_output(rito(format!("bad bob command: {}", next_command_full))).unwrap(); }
            };

            /*match tokens.next() {
                Some("Copied") => {
                    if config.automatic_builds {
                        let section = tokens.next().unwrap().split(" ").next().unwrap();
                        send_build_chain(section, false, &sender);
                    }
                },
                Some("Build") => {
                    let section = tokens.next().unwrap().split(" ").next().unwrap();
                    send_build_chain(section, false, &sender);
                },
                Some("Rebuild") => {
                    let section = tokens.next().unwrap().split(" ").next().unwrap();
                    send_build_chain(section, true, &sender);
                },
                Some("CoreFixMosaicStage") => {
                    let mut args = tokens.next().unwrap().split(" ");
                    let volume = args.next().unwrap().to_string();
                    let sections: Vec<String> = args.map(|s| s.to_string()).collect();
                    send_core_fixmosaic_stage(volume, sections, &sender);
                },
                // Send snapshots to #tem-bot as images
                Some("Snapshot") => {
                    let snapshot_name = tokens.next().unwrap();
                    let snapshot_path = format!(r#"{}\{}"#, config.dropbox_dir, snapshot_name);
                    run_chain_and_save_output(
                        CommandChain {
                            commands: vec![
                                rito_image(snapshot_path),
                            ],

                            label: format!("snapshot -> slack for {}", snapshot_name)
                        }).unwrap();
                },
                // Merge automatically-built RC3 sections with the full volume
                Some("Merge") => {
                    let section = tokens.next().unwrap();
                    send_rc3_merge_chain(section.to_string(), &sender);
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
                        label: format!("bob queue file {}", queue_file)
                    }).unwrap();
                },
                // Add a raw shell command to the queue (i.e. RC3Align)
                Some("Raw") => {
                    let command_string = tokens.next().unwrap();
                    let command:Vec<String> = command_string.split("~").map(|arg| arg.trim().to_string()).collect();
                    sender.send(CommandChain {
                        commands: vec![
                            command,
                        ],
                        label: format!("raw command '{}'", command_string),
                    }).unwrap();
                },
                // Deploy a core capture volume
                Some("Deploy") => {
                    let volume = tokens.next().unwrap();
                    send_core_deploy_chain(volume.to_string(), &sender);
                },
                // This case will be used even if there's no colon in the message
                Some(other_label) => {
                    println!("{}", other_label);
                    run_and_print_output(rito(next_command)).unwrap();
                },
                // This case should never be used
                None => ()
            }*/
        }
    })
}

fn main() {
    let config = config_from_yaml();

    // Create a channel for all Bob commands to be sent safely to a command processor thread:
    let (command_sender, command_receiver) = channel();

    // Create a channel for all Bob jobs to be sent safely to a single worker thread as CommandChains:
    let (chain_sender, chain_receiver) = channel();

    spawn_command_thread(command_receiver, chain_sender);
    spawn_worker_threadpool(chain_receiver);    

    if config.process_tem_output {
        // Two threads simply monitor the notification text files from the TEMs,
        // and will send lines from them to the command processor thread
        spawn_tem_message_reader_thread("TEM1", command_sender.clone());
        spawn_tem_message_reader_thread("TEM2", command_sender.clone());
    }

    // The CLI thread listens for manually entered CommandChains via queues or raw commands
    spawn_cli_thread(command_sender.clone()).join().unwrap();
}