![CI](https://github.com/Msc-Tecnologia/SRPK/workflows/CI/badge.svg)
# MSC SRPK v3.1 - Self-Referencing Proprietary Knowledge Graph

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Build Status](https://img.shields.io/github/workflow/status/your-org/srpk/CI)](https://github.com/your-org/srpk/actions)
[![Code Quality](https://img.shields.io/badge/code%20quality-A+-green.svg)](https://github.com/your-org/srpk)

## 🚀 Overview

MSC SRPK (Self-Referencing Proprietary Knowledge) Graph v3.1 is an enterprise-grade Python code analysis system that provides comprehensive metrics, security analysis, and intelligent code understanding through advanced graph algorithms and machine learning embeddings.

### Key Features

- 🔍 **Advanced Code Analysis**: Cyclomatic complexity, cognitive complexity, Halstead metrics
- 🛡️ **Security Scanning**: Detection of vulnerabilities and security anti-patterns
- 🧪 **Automated Test Generation**: Creates unit tests for functions and classes
- 📊 **Code Quality Metrics**: Maintainability index, code smells detection
- 🤖 **ML-Powered Embeddings**: Semantic code similarity using transformers
- ⚡ **Performance Optimized**: Parallel processing, intelligent caching
- 📈 **Enterprise Reporting**: HTML, JSON, and Markdown reports

## 📋 Requirements

### Core Dependencies
```txt
Python >= 3.8
torch >= 1.9.0
numpy >= 1.19.0
psutil >= 5.8.0
```

### Optional Dependencies
```txt
transformers  # For semantic embeddings
pytest       # For test generation
plotly       # For interactive charts
toml         # For TOML configuration
yaml         # For YAML configuration
```

## 🔧 Installation

### Standard Installation
```bash
# Clone repository
git clone https://github.com/your-org/srpk.git
cd srpk

# Install dependencies
pip install -r requirements.txt

# Run setup
python setup.py install
```

### Docker Installation
```bash
docker pull your-org/srpk:3.1
docker run -v /your/project:/app your-org/srpk:3.1
```

## 🚦 Quick Start

### Basic Usage
```bash
# Analyze a Python project
python srpk_v3_1.py /path/to/your/project

# With custom configuration
python srpk_v3_1.py /path/to/project --config .srpk.toml

# Generate specific report format
python srpk_v3_1.py /path/to/project --format html
```

### Python API
```python
from srpk_v3_1 import EnterpriseSRPKGraph, ConfigurationManager

# Initialize with configuration
config = ConfigurationManager()
graph = EnterpriseSRPKGraph(config)

# Analyze project
results = graph.analyze_project("/path/to/project")

# Get quality metrics
for node_id in graph.nodes:
    report = graph.get_node_quality_report(node_id)
    print(f"Quality Score: {report['quality_score']}")
```

## ⚙️ Configuration

Create a `.srpk.toml` file in your project root:

```toml
[analysis]
max_file_size_mb = 10
max_memory_usage_gb = 4
timeout_per_file_seconds = 30
excluded_dirs = [".git", ".venv", "__pycache__"]
parallel_processing = true
max_workers = 4

[metrics.security]
enabled = true
severity_levels = { eval = "critical", exec = "critical" }

[embedding]
model_type = "semantic"
vector_size = 768
use_cache = true

[cache]
enabled = true
directory = ".srpk_cache"
max_age_days = 30
```

## 💰 Pricing Plans

### Open Source Edition - Free
- ✅ Basic code analysis
- ✅ Complexity metrics
- ✅ JSON/Markdown reports
- ✅ Community support
- ⚠️ Limited to 100 files per analysis
- ⚠️ No security scanning
- ⚠️ No ML embeddings

### Professional - $49/month
- ✅ Everything in Open Source
- ✅ Security vulnerability scanning
- ✅ Code smell detection
- ✅ HTML interactive reports
- ✅ Unlimited file analysis
- ✅ Email support
- ✅ Caching system
- ⚠️ Single user license

### Enterprise - $299/month
- ✅ Everything in Professional
- ✅ ML-powered semantic analysis
- ✅ Automated test generation
- ✅ Custom security rules
- ✅ API access
- ✅ Priority support
- ✅ Team licenses (up to 10 users)
- ✅ CI/CD integration
- ✅ Advanced analytics dashboard

### Custom Enterprise - Contact Sales
- ✅ Everything in Enterprise
- ✅ On-premises deployment
- ✅ Custom integrations
- ✅ Dedicated support engineer
- ✅ SLA guarantees
- ✅ Unlimited users
- ✅ Training and onboarding
- ✅ Custom feature development

## 📊 Metrics Explained

### Cyclomatic Complexity
Measures the number of linearly independent paths through code. Lower is better.
- **Good**: < 10
- **Moderate**: 10-20
- **Complex**: > 20

### Cognitive Complexity
Measures how difficult code is to understand. Considers nesting and flow breaks.
- **Simple**: < 15
- **Moderate**: 15-30
- **Complex**: > 30

### Maintainability Index
Microsoft's maintainability metric (0-100). Higher is better.
- **Good**: > 80
- **Moderate**: 60-80
- **Poor**: < 60

## 🔒 Security Scanning

SRPK detects various security vulnerabilities:
- SQL injection patterns
- Command injection risks
- Hardcoded credentials
- Insecure deserialization
- Path traversal vulnerabilities
- XXE vulnerabilities
- Insecure random generation
- SSL/TLS misconfigurations

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

```bash
# Fork the repository
# Create your feature branch
git checkout -b feature/amazing-feature

# Commit your changes
git commit -m 'Add amazing feature'

# Push to the branch
git push origin feature/amazing-feature

# Open a Pull Request
```

## 📝 License

This software is proprietary and confidential. See [LICENSE](LICENSE) for details.

## 🆘 Support

- 📧 Email: msc.framework@gmail.com
- 💬 Discord: [Join our community](https://discord.gg/srpk)
- 📚 Documentation: [docs.msc-srpk.com](https://docs.msc-srpk.com)
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/srpk/issues)


## 📈 Performance Benchmarks

| Project Size | Files | Analysis Time | Memory Usage |
|-------------|-------|---------------|--------------|
| Small       | 100   | 5 seconds     | 200 MB       |
| Medium      | 1000  | 45 seconds    | 800 MB       |
| Large       | 5000  | 3 minutes     | 2 GB         |
| Enterprise  | 10000+| 8 minutes     | 4 GB         |

## 🗺️ Roadmap

### Q1 2025
- [ ] Real-time analysis mode
- [ ] VS Code extension
- [ ] GitHub Actions integration

### Q2 2025
- [ ] Multi-language support (JavaScript, TypeScript)
- [ ] AI-powered code review suggestions
- [ ]Cloud-based analysis platform

### Q3 2025
- [ ] Team collaboration features
- [ ] Historical metrics tracking
- [ ] Custom reporting templates

---

**MSC SRPK v3.1** - Empowering developers with intelligent code analysis 🚀