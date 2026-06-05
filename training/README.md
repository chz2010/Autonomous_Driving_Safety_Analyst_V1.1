# Local Qwen LoRA Training

This folder contains a small fine-tuning workflow for the free/open-source model.

The goal is **not** to teach Qwen the ISO standards from memory. The RAG database
already provides standards knowledge. The goal is to teach Qwen better behavior:

- detailed safety-case structure,
- function-level HARA coverage,
- clear S/E/C reasoning before ASIL/QM,
- separation of ISO 26262, ISO 21448 (SOTIF), and ISO 8800 views,
- engineering-specific recommendations and evidence limitations.

Generated data and LoRA outputs are ignored by git because they can contain
retrieved standards text.

---

## 1. Generate teacher examples locally

Make sure your local standards DB is already built:

```bash
python -m ingestion.standards_ingestion --embedding-backend local --reset
```

Generate a small smoke-test dataset first:

```bash
python training/generate_sft_dataset.py --limit 2
```

Generate the full seed dataset:

```bash
python training/generate_sft_dataset.py
```

Output:

```text
training/generated/qwen_sft.jsonl
```

Each record has:

```json
{
  "id": "lifecycle_lidar",
  "category": "item_safety_case",
  "messages": [
    {"role": "system", "content": "...local runtime prompt..."},
    {"role": "user", "content": "...question + retrieved context..."},
    {"role": "assistant", "content": "...ideal OpenAI teacher answer..."}
  ]
}
```

---

## 2. Fine-tune in Google Colab

Upload these files to Colab:

- `training/generated/qwen_sft.jsonl`
- `training/finetune_qwen_lora_colab.py`
- `training/requirements-colab.txt`

In Colab:

```bash
!pip install --upgrade -r requirements-colab.txt
!python finetune_qwen_lora_colab.py \
  --data qwen_sft.jsonl \
  --output qwen_safety_lora \
  --epochs 2
```

Recommended Colab runtime:

- GPU: T4 minimum, L4/A100 better.
- Base model: `Qwen/Qwen2.5-7B-Instruct` loaded in 4-bit.
- Default context length: 2048 tokens for T4/15 GB GPUs. Try 4096 only on L4/A100.
- Start with 30 examples and 2 epochs.

If a T4 still runs out of memory, retry with the smaller model:

```bash
!python finetune_qwen_lora_colab.py \
  --data qwen_sft.jsonl \
  --output qwen_safety_lora_3b \
  --base-model Qwen/Qwen2.5-3B-Instruct \
  --max-seq-length 2048 \
  --epochs 2
```

---

## 3. Evaluate before integrating

Keep 5-10 prompts out of training and compare:

1. current Qwen local mode,
2. LoRA-tuned Qwen,
3. OpenAI mode.

Use questions like:

- full lifecycle for lane maintaining perception,
- HARA for AEB pedestrian at night,
- dataset gaps for pedestrian/cyclist perception,
- SOTIF triggering conditions for faded lane markings,
- ISO 8800 release gates for AI perception.

In Colab, evaluate the trained adapter with:

```bash
!python evaluate_qwen_lora_colab.py \
  --adapter qwen_safety_lora \
  --prompt "Give me the whole safety lifecycle for developing an AEB pedestrian system according to ISO 26262, ISO 21448 (SOTIF), and ISO 8800."
```

For a live Streamlit demo of the fine-tuned option, serve the adapter from Colab:

```bash
!python serve_qwen_lora_colab.py \
  --adapter qwen_safety_lora \
  --max-input-tokens 4096 \
  --max-new-tokens 3000
```

Copy the printed Gradio API endpoint into your local `.env`:

```bash
LOCAL_LORA_API_URL=https://...gradio.live
```

Only integrate the adapter into the app if it improves structure and technical
depth without hallucinating clauses.

---

## 4. Deployment note

For AWS portfolio deployment, keep the OpenAI mode as the advanced/premium path.
The local LoRA model is best presented as a free draft mode:

- private/local-friendly,
- lower running cost,
- standards-only context,
- useful but not a replacement for expert review.

The current app calls Qwen through Ollama. A PEFT LoRA adapter cannot be loaded
directly by Ollama as-is. After evaluation, choose one integration path:

- Serve the LoRA model through a small Hugging Face/PyTorch endpoint on a GPU machine.
- Merge the adapter into the base model and convert the merged model to GGUF for Ollama.

Recommended independent local path:

1. Merge the adapter in Colab:

   ```bash
   !python merge_qwen_lora_colab.py \
     --adapter qwen_safety_lora \
     --output qwen_safety_merged
   ```

2. Save the merged model to Drive:

   ```bash
   !cp -r qwen_safety_merged /content/drive/MyDrive/qwen_safety_merged
   ```

3. Download/copy `qwen_safety_merged` into this project as:

   ```text
   training/models/qwen_safety_merged
   ```

4. Create the Ollama model locally:

   ```bash
   ollama create qwen-safety-lora \
     --experimental \
     --quantize q4_K_M \
     -f training/Modelfile.qwen-safety-lora.example
   ```

5. Restart Streamlit and choose `Local Qwen - after LoRA fine-tuning`.
