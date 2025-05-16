from plexus.reports.s3_utils import check_s3_bucket_access

@click.command('check-s3')
@click.option('--bucket', help='Optional bucket name to check (uses default if not specified)')
def test_s3_access(bucket):
    """Test if the S3 bucket for report block details is accessible."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
    
    console.print(Panel.fit("Testing S3 bucket access for report block details", title="S3 Access Test"))
    
    try:
        result = check_s3_bucket_access(bucket)
        
        table = Table(title=f"S3 Bucket: {result.get('bucket_name', 'Unknown')}")
        table.add_column("Test", style="cyan")
        table.add_column("Result", style="green")
        
        if "error" in result:
            table.add_row("Status", "[red]ERROR[/red]")
            table.add_row("Error", f"[red]{result['error']}[/red]")
        else:
            table.add_row("Bucket Exists", "[green]Yes[/green]" if result.get("bucket_exists") else "[red]No[/red]")
            table.add_row("Can List Objects", "[green]Yes[/green]" if result.get("can_list") else "[red]No[/red]")
            table.add_row("Can Write Files", "[green]Yes[/green]" if result.get("can_write") else "[red]No[/red]")
            table.add_row("Can Read Files", "[green]Yes[/green]" if result.get("can_read") else "[red]No[/red]")
            table.add_row("Can Delete Files", "[green]Yes[/green]" if result.get("can_delete") else "[red]No[/red]")
        
        console.print(table)
        
        if all([result.get(k) for k in ["bucket_exists", "can_list", "can_write", "can_read", "can_delete"]]):
            console.print("[green]✓ All S3 access tests passed. The bucket is fully accessible.[/green]")
            console.print("\nReport block details files should upload successfully.")
        else:
            console.print("[red]✗ S3 access test failed. See details above.[/red]")
            console.print("\nReport block details files may not upload successfully.")
            
    except Exception as e:
        console.print(f"[red]Error running test: {str(e)}[/red]")

report_group.add_command(test_s3_access) 