package expconf

// Configuration constants for task name generator.
const (
	TaskNameGeneratorWords = 3
	TaskNameGeneratorSep   = "-"
)

// Default task environment docker image names.
const (
	CPUImage  = "determinedai/environments-dev:py-3.8-pytorch-2-tf-2.11-cpu-1150a9b"
	CUDAImage = "determinedai/environments-dev:cuda-11.3-pytorch-2-tf-2.11-gpu-1150a9b"
	ROCMImage = "determinedai/environments-dev:rocm-5.0-pytorch-1.10-tf-2.7-rocm-1150a9b"
)
