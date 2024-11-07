## Plexus Dashboard

This is a Next.js/Shadcn dashboard built on Amplify Gen2 for Plexus, with a Python API client code and a CLI tool.

## CLI

To use the CLI, first set up your environment variables in a `.env` file:
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=... 
PLEXUS_API_URL=...
PLEXUS_ACCOUNT_KEY=...
```

Install the Plexus client Python module in development mode:
```
pip install -e .
```

Then run `plexus-dashboard` to see the available commands:
```
plexus-dashboard --help
```

## License

This library is licensed under the MIT-0 License. See the LICENSE file.