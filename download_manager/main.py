import sys
from rich.console import Console
from .config import config
from .ui.cli import CLI
from .downloaders import aria2c_manager
from .network import network_monitor

console = Console()

def main():
    try:
        config.load_settings()
        
        mode = "cli"
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            
        if mode == "server":
            from .api import run_server
            console.print("[green]Starting FastAPI Backend Server...[/green]")
            run_server()
        elif mode == "tui":
            from .ui.tui import DownloadTUI
            app = DownloadTUI()
            app.run()
        else:
            cli = CLI()
            cli.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        aria2c_manager.stop()
        network_monitor.stop()
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        aria2c_manager.stop()
        network_monitor.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
