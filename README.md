# RefWeaver

A tool for analyzing scientific manuscript introductions, identifying claims that require references, and assessing their verifiability.

## What It Does

1. **Input**: Takes a paragraph from a scientific manuscript introduction
2. **Analysis**: Identifies which sentences require a reference
3. **Search**: Looks for relevant references to support those claims
4. **Assessment**: Returns a verdict for each sentence:
   - ✅ **Keep** - Reference found, claim is supported
   - 📝 **Modify** - Reference found but claim needs to be more precise
   - ❌ **Delete** - No reference found, claim cannot be verified

## Project Structure

```
refweaver/
├── src/
│   ├── __init__.py
│   ├── analyzer.py      # Sentence analysis & claim detection
│   ├── searcher.py      # Reference search functionality
│   └── assessor.py      # Assessment & verdict generation
├── tests/
├── data/                # Sample manuscripts for testing
├── docs/                # Documentation
└── requirements.txt
```

## Status

🚧 Work in progress - initial setup phase

## Podman Compose

Required environment variables:
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `DB_PASSWORD`

Run the stack:
```
podman compose up --build
```

Health check:
```
curl http://localhost:8000/health
```

## License

MIT
