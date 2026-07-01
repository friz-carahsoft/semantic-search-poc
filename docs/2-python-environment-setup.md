# Step 2: Python Environment Setup

This guide sets up a clean Python environment for the semantic-search proof of concept.

## Goal

By the end of this step, you should be able to:

- Create an isolated Python virtual environment
- Install the packages needed for embeddings and OpenSearch access
- Verify that Python, PyTorch, Sentence Transformers, and `opensearch-py` are working

## Recommended Python Version

Use Python `3.12` or `3.13` if you want the safest path for a shared project setup.

Notes:

- Python `3.14` may also work, especially for local development, but some packages in the ML ecosystem can take time to fully settle on the newest Python release.
- If you already have Python `3.14.x` installed, you can try it first.
- If package installation fails on `3.14`, fall back to `3.12` or `3.13`.

## 1. Verify Python is installed

Run:

```bash
python3 --version
```

You should see Python `3.10+`. For this project, `3.12` or `3.13` is recommended.

## 2. Create a virtual environment

From the project root:

```bash
python3 -m venv .venv
```

This creates a local virtual environment in a folder named `.venv`.

## 3. Activate the virtual environment

### macOS or Linux

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```cmd
.venv\Scripts\activate.bat
```

After activation, your shell prompt should usually show `(.venv)`.

## 4. Upgrade packaging tools

With the virtual environment active, run:

```bash
python -m pip install --upgrade pip setuptools wheel
```

## 5. Install project dependencies

For this POC, install the minimum packages needed to:

- generate embeddings
- connect to OpenSearch
- prepare simple sample data

Run:

```bash
python -m pip install sentence-transformers opensearch-py pandas
```

What these packages are for:

- `sentence-transformers`: generates text embeddings
- `opensearch-py`: Python client for OpenSearch
- `pandas`: convenient for loading and shaping small datasets

## 6. Verify the installs

Run:

```bash
python -c "import torch; import sentence_transformers; import opensearchpy; import pandas; print('Python packages installed successfully')"
```

If that succeeds, the core dependencies are available.

## 7. Verify PyTorch is working

Run:

```bash
python -c "import torch; print(torch.__version__); print(torch.rand(2, 2))"
```

You should see:

- a PyTorch version number
- a small random tensor

That confirms the PyTorch dependency installed correctly.

## 8. Optional: verify GPU availability

Most people can complete this POC on CPU only. If you want to check whether PyTorch can see a GPU, run:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

Notes:

- On many laptops and desktops, this will print `False`, which is fine for this POC.
- On Apple Silicon Macs, PyTorch may use Metal acceleration, but CPU execution is still acceptable for a small dataset.

## 9. Test a simple embedding locally

Run:

```bash
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); emb = model.encode('Semantic search is useful.'); print(len(emb))"
```

This does two useful checks:

- downloads a small pre-trained embedding model
- confirms you can generate an embedding vector locally

The command should print the embedding dimension as an integer.

## 10. Freeze the environment for reproducibility

Once the environment is working, capture the installed package versions:

```bash
python -m pip freeze > requirements.txt
```

This creates a `requirements.txt` file that peers can use later with:

```bash
python -m pip install -r requirements.txt
```

For a public repo, this is the easiest way to make the setup reproducible after you confirm the environment works.

## 11. Deactivate the virtual environment

When you are done working in the environment:

```bash
deactivate
```

## Troubleshooting

### `python3` is not found

Install Python from one of the standard sources for your operating system, then rerun:

```bash
python3 --version
```

### Virtual environment activation fails on Windows PowerShell

Your system may block local scripts by default. Open PowerShell and review the current execution policy before changing anything. If your team uses Windows heavily, you may want to add a short Windows-specific note to the repo later.

### Package install fails on Python 3.14

If one of the ML dependencies fails to install, switch to Python `3.12` or `3.13` and repeat the setup steps.

### Model download fails

The first `SentenceTransformer(...)` run downloads model files from Hugging Face. If that step fails:

- confirm you have internet access
- retry the command
- check whether your network requires proxy configuration

### Import succeeds, but embedding generation is slow

That is normal on CPU for a local proof of concept. The sample dataset is small enough that CPU performance should still be acceptable.

## Result

After this step, your Python environment should be ready for the next phase: creating the sample dataset and generating embeddings for indexing into OpenSearch.
