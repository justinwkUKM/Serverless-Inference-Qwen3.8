variable "deployment_name" {
  type        = string
  description = "Verda serverless deployment name"
  default     = "qwen38-27b-nvfp4"
}

variable "model_id" {
  type        = string
  description = "Hugging Face model repository"
  default     = "unsloth/Qwen3.8-27B-NVFP4"
}

variable "gpu_type" {
  type        = string
  description = "Verda Serverless GPU identifier"
  default     = "RTX PRO 6000"
}

variable "max_model_len" {
  type        = number
  description = "Maximum model context window"
  default     = 32768
}

variable "max_replicas" {
  type        = number
  description = "Maximum number of serverless replicas"
  default     = 1
}

variable "min_replicas" {
  type        = number
  description = "Minimum serverless replicas; use 1 only for the always-warm experiment"
  default     = 0

  validation {
    condition     = var.min_replicas >= 0 && var.min_replicas <= var.max_replicas
    error_message = "min_replicas must be between zero and max_replicas."
  }
}

variable "max_num_batched_tokens" {
  type        = number
  description = "vLLM scheduler token budget per iteration"
  default     = 16384

  validation {
    condition     = contains([8192, 16384, 32768], var.max_num_batched_tokens)
    error_message = "max_num_batched_tokens must be 8192, 16384, or 32768 for the controlled TTFT experiment."
  }
}

variable "enable_chunked_prefill" {
  type        = bool
  description = "Explicitly enable vLLM chunked prefill"
  default     = true
}

variable "mixed_prefill_tuning" {
  type        = bool
  description = "Allow short prompts to advance around long partial prefills"
  default     = false
}
