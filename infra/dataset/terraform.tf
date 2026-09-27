terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  required_version = "~> 1.16.0"
  backend "s3" {
    bucket = "placeholder-tfstate-bucket"
    key    = "placeholder/service/dataset/terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
      Purpose   = "dataset-snapshots"
    }
  }
}
