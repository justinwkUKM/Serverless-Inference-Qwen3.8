resource "verda_container" "qwen38" {
  name = var.deployment_name

  compute = {
    name = var.gpu_type
    size = 1
  }

  scaling = {
    min_replica_count               = var.min_replicas
    max_replica_count               = var.max_replicas
    queue_message_ttl_seconds       = 900
    deadline_seconds                = 900
    concurrent_requests_per_replica = 4

    scale_up_policy = {
      delay_seconds = 1
    }

    scale_down_policy = {
      delay_seconds = 300
    }

    queue_load = {
      threshold = 1
    }
  }

  containers = [
    {
      # Pin a versioned x86_64 CUDA 12.9 image. Verda rejects moving tags.
      image        = "vllm/vllm-openai:v0.26.0-cu129-ubuntu2404"
      exposed_port = 8000

      entrypoint_overrides = {
        enabled = true
        cmd = concat([
          "--model",
          var.model_id,
          "--served-model-name",
          "qwen3.8-27b",
          "--tensor-parallel-size",
          "1",
          "--max-model-len",
          tostring(var.max_model_len),
          "--kv-cache-dtype",
          "fp8",
          "--gpu-memory-utilization",
          "0.90",
          "--enable-prefix-caching",
          "--max-num-batched-tokens",
          tostring(var.max_num_batched_tokens),
          "--reasoning-parser",
          "qwen3",
          "--default-chat-template-kwargs",
          jsonencode({ enable_thinking = false }),
          "--enable-auto-tool-choice",
          "--tool-call-parser",
          "qwen3_coder"
          ], var.enable_chunked_prefill ? ["--enable-chunked-prefill"] : [], var.mixed_prefill_tuning ? [
          "--max-num-partial-prefills",
          "2",
          "--max-long-partial-prefills",
          "1",
          "--long-prefill-token-threshold",
          "4096"
        ] : [])
      }

      env = [
        {
          type                         = "plain"
          name                         = "HF_HOME"
          value_or_reference_to_secret = "/data/hf-cache"
        }
      ]

      volume_mounts = [
        {
          type       = "scratch"
          mount_path = "/data"
          size_in_mb = 102400
        }
      ]

      healthcheck = {
        enabled = "true"
        port    = "8000"
        path    = "/health"
      }
    }
  ]

  is_spot = false
}
