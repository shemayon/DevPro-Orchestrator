#!/usr/bin/env python3
"""Multi-Agent Orchestration CLI.

Command-line interface for managing the LangGraph multi-agent system.
Provides commands for task execution, batch processing, monitoring, and reporting.
"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .supervisor import Supervisor as LibrarySupervisor
from .supervisor_executor import SupervisorExecutor
from .task_manager import TaskManager

# Initialize CLI and console
app = typer.Typer(help="Multi-Agent Orchestration System CLI")
console = Console()


class MultiAgentCLI:
    """CLI interface for multi-agent orchestration."""

    def __init__(self):
        """Initialize CLI with default components."""
        self.orchestrator: LibrarySupervisor | None = None
        self.executor: SupervisorExecutor | None = None
        self.task_manager = TaskManager()

    async def initialize_orchestrator(self):
        """Initialize the orchestrator if not already done."""
        if not self.orchestrator:
            self.orchestrator = LibrarySupervisor()

    async def initialize_executor(self, config: dict | None = None):
        """Initialize the supervisor executor if not already done."""
        await self.initialize_orchestrator()
        if not self.executor:
            self.executor = SupervisorExecutor(self.orchestrator, config)

    async def cleanup(self):
        """Cleanup resources."""
        if self.orchestrator:
            await self.orchestrator.close()


# Global CLI instance
cli_instance = MultiAgentCLI()


@app.command()
def status():
    """Show system status and agent information."""

    async def _status():
        try:
            await cli_instance.initialize_orchestrator()

            with console.status("[bold green]Getting system status..."):
                status_info = await cli_instance.orchestrator.get_agent_status()

            # Display system status
            console.print(
                Panel.fit(
                    f"[bold green]System Status: "
                    f"{status_info['system_status'].upper()}[/bold green]\n"
                    f"Last Updated: {status_info['last_updated'][:19]}",
                    title="🤖 Multi-Agent Orchestration System",
                )
            )

            # Display agent status
            agent_table = Table(
                title="Agent Status", show_header=True, header_style="bold magenta"
            )
            agent_table.add_column("Agent", style="cyan")
            agent_table.add_column("Status", style="green")
            agent_table.add_column("Model/Tools", style="yellow")

            for agent_name, agent_info in status_info["agents"].items():
                model_info = agent_info.get("model", agent_info.get("tools", "N/A"))
                if isinstance(model_info, list):
                    model_info = ", ".join(model_info)

                agent_table.add_row(
                    agent_name.title(), agent_info["status"].upper(), str(model_info)
                )

            console.print(agent_table)

            # Display task statistics
            stats = status_info["task_statistics"]
            stats_table = Table(
                title="Task Statistics", show_header=True, header_style="bold blue"
            )
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="white")

            stats_table.add_row("Total Tasks", str(stats["total_tasks"]))
            stats_table.add_row(
                "Completed",
                f"{stats['completed_tasks']} ({stats['completion_percentage']:.1f}%)",
            )
            stats_table.add_row("In Progress", str(stats["in_progress_tasks"]))
            stats_table.add_row("Blocked", str(stats["blocked_tasks"]))
            stats_table.add_row("Not Started", str(stats["not_started_tasks"]))
            stats_table.add_row("Total Hours", f"{stats['total_estimated_hours']:.1f}")
            stats_table.add_row("Remaining Hours", f"{stats['remaining_hours']:.1f}")

            console.print(stats_table)

        except Exception as e:
            console.print(f"[bold red]Error getting status: {e}[/bold red]")
        finally:
            await cli_instance.cleanup()

    asyncio.run(_status())


@app.command()
def execute_task(
    task_id: int = typer.Argument(..., help="ID of the task to execute"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Execute a single task through the multi-agent workflow."""

    async def _execute_task():
        try:
            await cli_instance.initialize_orchestrator()

            console.print(f"[bold blue]Executing task {task_id}...[/bold blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Executing task...", total=None)

                result = await cli_instance.orchestrator.execute_task(task_id)
                progress.remove_task(task)

            if result.get("success"):
                console.print(
                    f"[bold green]✓ Task {task_id} completed successfully![/bold green]"
                )

                if verbose:
                    # Show agent outputs
                    agent_outputs = result.get("agent_outputs", {})
                    if agent_outputs:
                        console.print("\n[bold yellow]Agent Outputs:[/bold yellow]")
                        for agent_name, output in agent_outputs.items():
                            console.print(f"\n[cyan]{agent_name.title()} Agent:[/cyan]")
                            if isinstance(output, dict):
                                console.print(
                                    f"  Status: {output.get('status', 'unknown')}"
                                )
                                console.print(
                                    f"  Duration: "
                                    f"{output.get('duration_minutes', 0):.1f} minutes"
                                )
                                if "artifacts_created" in output:
                                    artifacts = output["artifacts_created"]
                                    if artifacts:
                                        console.print(
                                            f"  Artifacts: {', '.join(artifacts)}"
                                        )

            else:
                console.print(
                    f"[bold red]✗ Task {task_id} failed: "
                    f"{result.get('error', 'Unknown error')}[/bold red]"
                )

                if verbose and result.get("error_context"):
                    console.print("\n[yellow]Error Details:[/yellow]")
                    for key, value in result["error_context"].items():
                        console.print(f"  {key}: {value}")

        except Exception as e:
            console.print(f"[bold red]Error executing task: {e}[/bold red]")
        finally:
            await cli_instance.cleanup()

    asyncio.run(_execute_task())


@app.command()
def batch_execute(
    batch_size: int = typer.Option(5, "--size", "-s", help="Number of tasks in batch"),
    max_concurrent: int = typer.Option(
        3, "--concurrent", "-c", help="Maximum concurrent tasks"
    ),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Task timeout in minutes"),
    export_report: str | None = typer.Option(
        None, "--export", "-e", help="Export report to file"
    ),
):
    """Execute a batch of ready tasks autonomously."""

    async def _batch_execute():
        try:
            # Configure batch execution
            config = {
                "batch_size": batch_size,
                "max_concurrent_tasks": max_concurrent,
                "timeout_minutes": timeout,
            }

            await cli_instance.initialize_executor(config)

            console.print(
                f"[bold blue]Starting batch execution "
                f"(size: {batch_size})...[/bold blue]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Executing batch...", total=None)

                report = await cli_instance.executor.execute_autonomous_batch()
                progress.remove_task(task)

            # Display batch results
            console.print(
                Panel.fit(
                    f"[bold green]Batch ID: {report.batch_id}[/bold green]\n"
                    f"Total Tasks: {report.total_tasks}\n"
                    f"Completed: {report.completed_tasks}\n"
                    f"Failed: {report.failed_tasks}\n"
                    f"Success Rate: {report.success_rate:.1%}\n"
                    f"Duration: {report.total_duration_minutes:.1f} minutes",
                    title="📊 Batch Execution Results",
                )
            )

            # Show agent performance
            if report.agent_performance:
                perf_table = Table(
                    title="Agent Performance",
                    show_header=True,
                    header_style="bold green",
                )
                perf_table.add_column("Agent", style="cyan")
                perf_table.add_column("Tasks", style="white")
                perf_table.add_column("Success Rate", style="green")
                perf_table.add_column("Avg Duration", style="yellow")

                for agent_name, perf in report.agent_performance.items():
                    perf_table.add_row(
                        agent_name.title(),
                        f"{perf['tasks_completed']}/{perf['tasks_executed']}",
                        f"{perf['success_rate']:.1%}",
                        f"{perf['average_duration_minutes']:.1f}m",
                    )

                console.print(perf_table)

            # Show recommendations
            if report.recommendations:
                console.print("\n[bold yellow]Recommendations:[/bold yellow]")
                for rec in report.recommendations:
                    console.print(f"  • {rec}")

            # Export report if requested
            if export_report:
                try:
                    cli_instance.executor.export_batch_report(
                        report.batch_id, export_report
                    )
                    console.print(
                        f"\n[green]Report exported to: {export_report}[/green]"
                    )
                except Exception as e:
                    console.print(f"\n[red]Error exporting report: {e}[/red]")

        except Exception as e:
            console.print(f"[bold red]Error executing batch: {e}[/bold red]")
        finally:
            await cli_instance.cleanup()

    asyncio.run(_batch_execute())


@app.command()
def continuous_batch(
    max_batches: int = typer.Option(
        10, "--batches", "-b", help="Maximum number of batches"
    ),
    interval: int = typer.Option(
        30, "--interval", "-i", help="Interval between batches (minutes)"
    ),
    batch_size: int = typer.Option(5, "--size", "-s", help="Tasks per batch"),
    export_dir: str | None = typer.Option(
        None, "--export-dir", "-e", help="Directory to export reports"
    ),
):
    """Execute multiple batches continuously."""

    async def _continuous_batch():
        try:
            config = {"batch_size": batch_size}
            await cli_instance.initialize_executor(config)

            console.print(
                "[bold blue]Starting continuous batch execution...[/bold blue]"
            )
            console.print(f"Max Batches: {max_batches}, Interval: {interval} minutes")

            reports = await cli_instance.executor.execute_continuous_batches(
                max_batches=max_batches, interval_minutes=interval
            )

            # Summary table
            summary_table = Table(
                title="Continuous Batch Summary",
                show_header=True,
                header_style="bold blue",
            )
            summary_table.add_column("Batch", style="cyan")
            summary_table.add_column("Tasks", style="white")
            summary_table.add_column("Success Rate", style="green")
            summary_table.add_column("Duration", style="yellow")

            total_tasks = 0
            total_successful = 0

            for i, report in enumerate(reports):
                total_tasks += report.total_tasks
                total_successful += report.completed_tasks

                summary_table.add_row(
                    f"Batch {i + 1}",
                    str(report.total_tasks),
                    f"{report.success_rate:.1%}",
                    f"{report.total_duration_minutes:.1f}m",
                )

            console.print(summary_table)

            # Overall summary
            overall_success_rate = (
                total_successful / total_tasks if total_tasks > 0 else 0
            )
            console.print(
                Panel.fit(
                    f"[bold green]Overall Results[/bold green]\n"
                    f"Total Batches: {len(reports)}\n"
                    f"Total Tasks: {total_tasks}\n"
                    f"Total Successful: {total_successful}\n"
                    f"Overall Success Rate: {overall_success_rate:.1%}",
                    title="📈 Continuous Execution Summary",
                )
            )

            # Export reports if directory provided
            if export_dir:
                export_path = Path(export_dir)
                export_path.mkdir(parents=True, exist_ok=True)

                for report in reports:
                    report_file = export_path / f"{report.batch_id}_report.json"
                    cli_instance.executor.export_batch_report(
                        report.batch_id, str(report_file)
                    )

                console.print(f"\n[green]All reports exported to: {export_dir}[/green]")

        except Exception as e:
            console.print(f"[bold red]Error in continuous execution: {e}[/bold red]")
        finally:
            await cli_instance.cleanup()

    asyncio.run(_continuous_batch())


@app.command()
def list_tasks(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum number of tasks to show"
    ),
):
    """List tasks from the database."""
    try:
        if status:
            tasks = cli_instance.task_manager.get_tasks_by_status(status)[:limit]
            title = f"Tasks with status: {status}"
        else:
            # Get all ready tasks by default
            tasks = cli_instance.task_manager.get_ready_tasks()[:limit]
            title = "Ready Tasks"

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return

        # Create tasks table
        task_table = Table(title=title, show_header=True, header_style="bold magenta")
        task_table.add_column("ID", style="cyan")
        task_table.add_column("Title", style="white", max_width=40)
        task_table.add_column("Component", style="green")
        task_table.add_column("Priority", style="yellow")
        task_table.add_column("Status", style="blue")

        for task in tasks:
            # Truncate long titles
            title_text = task["title"]
            if len(title_text) > 37:
                title_text = title_text[:34] + "..."

            task_table.add_row(
                str(task["id"]),
                title_text,
                task["component_area"],
                task["priority"],
                task["status"],
            )

        console.print(task_table)

        if len(tasks) == limit:
            console.print(
                f"[dim]Showing first {limit} tasks. Use --limit to see more.[/dim]"
            )

    except Exception as e:
        console.print(f"[bold red]Error listing tasks: {e}[/bold red]")


@app.command()
def task_info(
    task_id: int = typer.Argument(..., help="ID of the task to show"),
):
    """Show detailed information about a specific task."""
    try:
        # Get task data
        with cli_instance.task_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            task = cursor.fetchone()

        if not task:
            console.print(f"[bold red]Task {task_id} not found[/bold red]")
            return

        task_dict = dict(task)

        # Display task details
        console.print(
            Panel.fit(
                f"[bold blue]ID:[/bold blue] {task_dict['id']}\n"
                f"[bold blue]Title:[/bold blue] {task_dict['title']}\n"
                f"[bold blue]Component:[/bold blue] {task_dict['component_area']}\n"
                f"[bold blue]Phase:[/bold blue] {task_dict['phase']}\n"
                f"[bold blue]Priority:[/bold blue] {task_dict['priority']}\n"
                f"[bold blue]Status:[/bold blue] {task_dict['status']}\n"
                f"[bold blue]Complexity:[/bold blue] {task_dict['complexity']}\n"
                f"[bold blue]Estimated Hours:[/bold blue] "
                f"{task_dict['time_estimate_hours']}\n"
                f"[bold blue]Created:[/bold blue] {task_dict['created_at']}\n"
                f"[bold blue]Updated:[/bold blue] {task_dict['updated_at']}",
                title=f"📋 Task {task_id} Details",
            )
        )

        # Show description
        if task_dict["description"]:
            console.print(
                Panel(
                    task_dict["description"], title="Description", border_style="green"
                )
            )

        # Show success criteria
        if task_dict["success_criteria"]:
            console.print(
                Panel(
                    task_dict["success_criteria"],
                    title="Success Criteria",
                    border_style="yellow",
                )
            )

        # Show dependencies
        dependencies = cli_instance.task_manager.get_task_dependencies(task_id)
        if dependencies:
            dep_table = Table(
                title="Dependencies", show_header=True, header_style="bold red"
            )
            dep_table.add_column("Depends On", style="cyan")
            dep_table.add_column("Title", style="white")
            dep_table.add_column("Status", style="green")

            for dep in dependencies:
                dep_table.add_row(
                    str(dep["depends_on_task_id"]),
                    dep["depends_on_title"],
                    dep["depends_on_status"],
                )

            console.print(dep_table)

        # Show recent progress
        progress = cli_instance.task_manager.get_task_progress(task_id)
        if progress:
            prog_table = Table(
                title="Recent Progress", show_header=True, header_style="bold green"
            )
            prog_table.add_column("Date", style="cyan")
            prog_table.add_column("Progress", style="green")
            prog_table.add_column("Notes", style="white")

            for prog in progress[:5]:  # Show last 5 entries
                prog_table.add_row(
                    prog["created_at"][:10],
                    f"{prog['progress_percentage']}%",
                    prog["notes"] or "",
                )

            console.print(prog_table)

    except Exception as e:
        console.print(f"[bold red]Error getting task info: {e}[/bold red]")


@app.command()
def agent_stats():
    """Show detailed agent performance statistics."""

    async def _agent_stats():
        try:
            config = {}
            await cli_instance.initialize_executor(config)

            stats = cli_instance.executor.get_agent_statistics()

            if not any(stat["total_tasks_executed"] > 0 for stat in stats.values()):
                console.print("[yellow]No agent execution data available yet[/yellow]")
                return

            # Agent statistics table
            stats_table = Table(
                title="Agent Performance Statistics",
                show_header=True,
                header_style="bold blue",
            )
            stats_table.add_column("Agent", style="cyan")
            stats_table.add_column("Total Tasks", style="white")
            stats_table.add_column("Successful", style="green")
            stats_table.add_column("Failed", style="red")
            stats_table.add_column("Success Rate", style="green")
            stats_table.add_column("Avg Duration", style="yellow")
            stats_table.add_column("Total Duration", style="yellow")

            for agent_name, stat in stats.items():
                if stat["total_tasks_executed"] > 0:
                    stats_table.add_row(
                        agent_name.title(),
                        str(stat["total_tasks_executed"]),
                        str(stat["successful_tasks"]),
                        str(stat["failed_tasks"]),
                        f"{stat['success_rate']:.1%}",
                        f"{stat['average_task_duration']:.1f}m",
                        f"{stat['total_duration_minutes']:.1f}m",
                    )

            console.print(stats_table)

            # Batch history
            history = cli_instance.executor.get_batch_history()
            if history:
                history_table = Table(
                    title="Recent Batch History",
                    show_header=True,
                    header_style="bold magenta",
                )
                history_table.add_column("Batch ID", style="cyan")
                history_table.add_column("Start Time", style="white")
                history_table.add_column("Tasks", style="green")
                history_table.add_column("Success Rate", style="green")
                history_table.add_column("Duration", style="yellow")

                for batch in history[:10]:  # Show last 10 batches
                    history_table.add_row(
                        batch["batch_id"],
                        batch["start_time"][:19],
                        str(batch["total_tasks"]),
                        f"{batch['success_rate']:.1%}",
                        f"{batch['duration_minutes']:.1f}m",
                    )

                console.print(history_table)

        except Exception as e:
            console.print(f"[bold red]Error getting agent stats: {e}[/bold red]")
        finally:
            await cli_instance.cleanup()

    asyncio.run(_agent_stats())


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    batch_size: int | None = typer.Option(
        None, "--batch-size", help="Set default batch size"
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", help="Set default timeout (minutes)"
    ),
    concurrent: int | None = typer.Option(
        None, "--concurrent", help="Set max concurrent tasks"
    ),
):
    """Manage system configuration."""
    config_file = Path.home() / ".ai_job_scraper_config.json"

    # Load existing config
    current_config = {}
    if config_file.exists():
        with config_file.open() as f:
            current_config = json.load(f)

    if show:
        console.print(
            Panel(
                json.dumps(current_config, indent=2)
                if current_config
                else "No configuration found",
                title="Current Configuration",
                border_style="blue",
            )
        )
        return

    # Update configuration
    updated = False
    if batch_size is not None:
        current_config["batch_size"] = batch_size
        updated = True
    if timeout is not None:
        current_config["timeout_minutes"] = timeout
        updated = True
    if concurrent is not None:
        current_config["max_concurrent_tasks"] = concurrent
        updated = True

    if updated:
        with config_file.open("w") as f:
            json.dump(current_config, f, indent=2)
        console.print(
            f"[green]Configuration updated and saved to {config_file}[/green]"
        )
    else:
        console.print("[yellow]No configuration changes specified[/yellow]")


@app.callback()
def main():
    """Multi-Agent Orchestration System CLI.

    Manage and monitor the LangGraph-based multi-agent system for autonomous
    task execution.
    """
    pass


if __name__ == "__main__":
    app()
