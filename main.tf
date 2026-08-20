resource "verda_container" "qwen38" {
  name = var.deployment_name

  compute = {
    name = var.gpu_type
    size = 1
  }

  scaling = {
    min_replica_count               = 0
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
      image        = "docker.io/vllm/vllm-openai:v0.26.0-cu129-ubuntu2404"
      exposed_port = 8000

      entrypoint_overrides = {
        enabled = true
        cmd = [
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
          "16384",
          "--reasoning-parser",
          "qwen3",
          "--enable-auto-tool-choice",
          "--tool-call-parser",
          "qwen3_coder"
        ]
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

  is_spot = true
}
