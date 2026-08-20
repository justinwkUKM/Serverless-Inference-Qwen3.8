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
