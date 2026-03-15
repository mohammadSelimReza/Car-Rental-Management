def generate_monthly_payouts_job():
    from super_admin.management.commands.generate_monthly_payouts import Command
    Command().handle()