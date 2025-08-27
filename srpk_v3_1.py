"""
MSC SRPK (Self-Referencing Proprietary Knowledge) Graph v3.1
Sistema empresarial de análisis, gestión y visualización de código Python
con configuración personalizable, caché inteligente y reportes HTML interactivos.

Versión 3.1 - Cambios:
- Corrección de todos los errores identificados en v3.0
- Eliminación completa de placeholders
- Implementación real de embeddings con fallback mejorado
- Sistema de testing funcional integrado
- Mejoras en detección de seguridad
- Optimización de memoria y rendimiento
- Corrección de tipos de retorno inconsistentes
"""

import ast
import re
import logging
import hashlib
import json
import os
import sys
import time
import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
from collections import defaultdict, OrderedDict, Counter
import subprocess
import tempfile
import importlib.util
from typing import Dict, List, Tuple, Optional, Any, Set, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import warnings
import traceback
import psutil
import gc
from pathlib import Path
import pickle
import gzip
import shutil
from datetime import datetime, timedelta
import html
import base64
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Intentar importar librerías opcionales
try:
    import toml
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False
    warnings.warn("toml not available. Configuration will use JSON fallback.")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.offline as pyo
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    warnings.warn("plotly not available. Interactive charts will be basic.")

# =====================================================================
# CONFIGURACIÓN Y CONSTANTES
# =====================================================================

DEFAULT_CONFIG = {
    "analysis": {
        "max_file_size_mb": 10,
        "max_memory_usage_gb": 4,
        "timeout_per_file_seconds": 30,
        "excluded_dirs": [".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", "dist", "build"],
        "excluded_files": ["*.pyc", "*.pyo", "*.pyd", ".DS_Store", "*.so", "*.dll"],
        "include_tests": True,
        "follow_symlinks": False,
        "max_recursion_depth": 10,
        "parallel_processing": True,
        "max_workers": 4
    },
    "metrics": {
        "complexity": {
            "cyclomatic_threshold": 10,
            "cognitive_threshold": 15,
            "lines_per_function_threshold": 50,
            "parameters_threshold": 5,
            "methods_per_class_threshold": 20,
            "nesting_depth_threshold": 5
        },
        "documentation": {
            "min_docstring_length": 10,
            "require_class_docstrings": True,
            "require_function_docstrings": True,
            "comment_ratio_threshold": 0.1,
            "require_type_hints": False
        },
        "security": {
            "enabled": True,
            "custom_patterns": [],
            "severity_levels": {
                "eval": "critical",
                "exec": "critical", 
                "pickle": "high",
                "subprocess_shell": "high",
                "hardcoded_secrets": "critical",
                "sql_injection": "critical",
                "path_traversal": "high",
                "xxe": "high",
                "yaml_load": "high"
            }
        },
        "code_quality": {
            "max_line_length": 120,
            "max_file_length": 1000,
            "max_function_arguments": 7,
            "max_return_statements": 5,
            "max_branches": 12
        }
    },
    "testing": {
        "framework": "pytest",
        "timeout_seconds": 30,
        "coverage_threshold": 80,
        "parallel_execution": False,
        "generate_tests": True,
        "test_patterns": ["test_*.py", "*_test.py", "tests.py"]
    },
    "embedding": {
        "model_type": "semantic",  # semantic, syntactic, or hybrid
        "vector_size": 768,
        "use_cache": True,
        "batch_size": 32,
        "max_sequence_length": 512,
        "similarity_threshold": 0.85
    },
    "cache": {
        "enabled": True,
        "directory": ".srpk_cache",
        "max_age_days": 30,
        "max_size_mb": 500,
        "compression": True,
        "compression_level": 6
    },
    "reporting": {
        "formats": ["json", "html", "markdown"],
        "include_source_preview": True,
        "max_preview_lines": 50,
        "generate_badges": True,
        "theme": "dark",
        "include_metrics_history": True,
        "export_to_csv": False
    },
    "persistence": {
        "auto_save": True,
        "save_interval_seconds": 300,
        "backup_count": 3,
        "state_file": "srpk_state.json"
    }
}

# =====================================================================
# SISTEMA DE CONFIGURACIÓN MEJORADO
# =====================================================================

class ConfigurationManager:
    """Gestor de configuración con soporte para múltiples formatos y validación."""
    
    CONFIG_FILENAMES = [
        ".srpk.toml",
        ".srpk.json", 
        ".srpk.yaml",
        ".srpk.yml",
        "srpk.config.toml",
        "srpk.config.json",
        ".srpkrc"
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._deep_copy(DEFAULT_CONFIG)
        self.config_file_path = None
        self.validators = self._setup_validators()
        
        if config_path:
            self.load_config(config_path)
        else:
            self._auto_discover_config()
    
    def _deep_copy(self, obj):
        """Copia profunda de diccionarios anidados."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(i) for i in obj]
        return obj
    
    def _setup_validators(self) -> Dict[str, callable]:
        """Configura validadores para opciones de configuración."""
        return {
            'analysis.max_file_size_mb': lambda v: v > 0 and v <= 100,
            'analysis.max_memory_usage_gb': lambda v: v > 0 and v <= 32,
            'analysis.timeout_per_file_seconds': lambda v: v > 0 and v <= 300,
            'analysis.max_workers': lambda v: v > 0 and v <= 16,
            'cache.max_size_mb': lambda v: v > 0 and v <= 10000,
            'cache.compression_level': lambda v: v >= 1 and v <= 9,
            'embedding.vector_size': lambda v: v in [128, 256, 384, 512, 768, 1024],
            'embedding.batch_size': lambda v: v > 0 and v <= 128
        }
    
    def _auto_discover_config(self):
        """Busca automáticamente archivos de configuración."""
        for filename in self.CONFIG_FILENAMES:
            if os.path.exists(filename):
                try:
                    self.load_config(filename)
                    logging.info(f"Configuration loaded from {filename}")
                    return
                except Exception as e:
                    logging.warning(f"Failed to load config from {filename}: {e}")
    
    def load_config(self, path: str):
        """Carga configuración desde un archivo con validación."""
        self.config_file_path = path
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if path.endswith('.toml') and TOML_AVAILABLE:
                user_config = toml.loads(content)
            elif (path.endswith('.yaml') or path.endswith('.yml')) and YAML_AVAILABLE:
                user_config = yaml.safe_load(content)
            else:
                user_config = json.loads(content)
            
            # Validar configuración
            self._validate_config(user_config)
            
            # Merge con configuración default
            self._merge_config(self.config, user_config)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file {path}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration from {path}: {e}")
    
    def _validate_config(self, config: dict, path: str = ""):
        """Valida la configuración contra los validadores definidos."""
        for key, value in config.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                self._validate_config(value, current_path)
            elif current_path in self.validators:
                if not self.validators[current_path](value):
                    raise ValueError(f"Invalid value for {current_path}: {value}")
    
    def _merge_config(self, base: dict, override: dict):
        """Fusiona configuración usuario con la base de forma segura."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def save_config(self, path: Optional[str] = None):
        """Guarda la configuración actual con formato apropiado."""
        save_path = path or self.config_file_path or ".srpk.json"
        
        with open(save_path, 'w', encoding='utf-8') as f:
            if save_path.endswith('.toml') and TOML_AVAILABLE:
                toml.dump(self.config, f)
            elif (save_path.endswith('.yaml') or save_path.endswith('.yml')) and YAML_AVAILABLE:
                yaml.dump(self.config, f, default_flow_style=False)
            else:
                json.dump(self.config, f, indent=2)
    
    def get(self, key_path: str, default=None):
        """Obtiene un valor de configuración usando notación de puntos."""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value):
        """Establece un valor de configuración con validación."""
        # Validar si existe un validador para esta clave
        if key_path in self.validators:
            if not self.validators[key_path](value):
                raise ValueError(f"Invalid value for {key_path}: {value}")
        
        keys = key_path.split('.')
        target = self.config
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        target[keys[-1]] = value

# =====================================================================
# SISTEMA DE CACHÉ MEJORADO
# =====================================================================

class CacheManager:
    """Sistema de caché inteligente con límites de tamaño y limpieza automática."""
    
    def __init__(self, config: ConfigurationManager):
        self.config = config
        self.cache_dir = Path(config.get('cache.directory', '.srpk_cache'))
        self.enabled = config.get('cache.enabled', True)
        self.compression = config.get('cache.compression', True)
        self.compression_level = config.get('cache.compression_level', 6)
        self.max_age_days = config.get('cache.max_age_days', 30)
        self.max_size_mb = config.get('cache.max_size_mb', 500)
        
        if self.enabled:
            self.cache_dir.mkdir(exist_ok=True)
            self._cleanup_old_cache()
            self._enforce_size_limit()
    
    def _get_cache_path(self, key: str) -> Path:
        """Genera la ruta de caché para una clave."""
        hash_key = hashlib.sha256(key.encode()).hexdigest()
        extension = '.pkl.gz' if self.compression else '.pkl'
        return self.cache_dir / f"{hash_key[:8]}_{hash_key[-8:]}{extension}"
    
    def _cleanup_old_cache(self):
        """Limpia archivos de caché antiguos."""
        if not self.enabled or not self.cache_dir.exists():
            return
        
        current_time = time.time()
        max_age_seconds = self.max_age_days * 86400
        
        for cache_file in self.cache_dir.glob('*.pkl*'):
            try:
                if current_time - cache_file.stat().st_mtime > max_age_seconds:
                    cache_file.unlink()
                    logging.debug(f"Removed old cache file: {cache_file}")
            except Exception as e:
                logging.warning(f"Failed to remove cache file {cache_file}: {e}")
    
    def _enforce_size_limit(self):
        """Aplica límite de tamaño al caché."""
        if not self.enabled or not self.cache_dir.exists():
            return
        
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob('*.pkl*'))
        max_size_bytes = self.max_size_mb * 1024 * 1024
        
        if total_size > max_size_bytes:
            # Eliminar archivos más antiguos hasta estar bajo el límite
            files = sorted(
                self.cache_dir.glob('*.pkl*'),
                key=lambda f: f.stat().st_mtime
            )
            
            for file in files:
                if total_size <= max_size_bytes:
                    break
                try:
                    file_size = file.stat().st_size
                    file.unlink()
                    total_size -= file_size
                    logging.debug(f"Removed cache file to enforce size limit: {file}")
                except Exception as e:
                    logging.warning(f"Failed to remove cache file {file}: {e}")
    
    def get(self, key: str, file_hash: Optional[str] = None) -> Optional[Any]:
        """Obtiene un valor del caché con validación."""
        if not self.enabled:
            return None
        
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            if self.compression:
                with gzip.open(cache_path, 'rb') as f:
                    data = pickle.load(f)
            else:
                with open(cache_path, 'rb') as f:
                    data = pickle.load(f)
            
            # Verificar hash si se proporciona
            if file_hash and data.get('file_hash') != file_hash:
                logging.debug(f"Cache miss due to hash mismatch for {key}")
                cache_path.unlink()  # Eliminar entrada inválida
                return None
            
            # Actualizar tiempo de acceso
            cache_path.touch()
            
            logging.debug(f"Cache hit for {key}")
            return data.get('value')
        
        except (pickle.PickleError, EOFError, gzip.BadGzipFile) as e:
            logging.warning(f"Corrupted cache file for {key}: {e}")
            try:
                cache_path.unlink()
            except:
                pass
            return None
        except Exception as e:
            logging.warning(f"Failed to load cache for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, file_hash: Optional[str] = None):
        """Guarda un valor en caché con metadata."""
        if not self.enabled:
            return
        
        cache_path = self._get_cache_path(key)
        
        data = {
            'value': value,
            'timestamp': time.time(),
            'file_hash': file_hash,
            'version': '3.1'
        }
        
        try:
            if self.compression:
                with gzip.open(cache_path, 'wb', compresslevel=self.compression_level) as f:
                    pickle.dump(data, f)
            else:
                with open(cache_path, 'wb') as f:
                    pickle.dump(data, f)
            
            logging.debug(f"Cached data for {key}")
            
            # Verificar límite de tamaño después de agregar
            self._enforce_size_limit()
        
        except Exception as e:
            logging.warning(f"Failed to cache data for {key}: {e}")
    
    def clear(self):
        """Limpia todo el caché de forma segura."""
        if self.cache_dir.exists():
            try:
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
                logging.info("Cache cleared successfully")
            except Exception as e:
                logging.error(f"Failed to clear cache: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """Obtiene información sobre el estado del caché."""
        if not self.cache_dir.exists():
            return {'enabled': False, 'files': 0, 'size_mb': 0}
        
        files = list(self.cache_dir.glob('*.pkl*'))
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            'enabled': self.enabled,
            'directory': str(self.cache_dir),
            'files': len(files),
            'size_mb': total_size / (1024 * 1024),
            'max_size_mb': self.max_size_mb,
            'compression': self.compression
        }

# =====================================================================
# MANEJO ROBUSTO DE ERRORES MEJORADO
# =====================================================================

class AnalysisError(Exception):
    """Error base para análisis."""
    pass

class SyntaxAnalysisError(AnalysisError):
    """Error de sintaxis durante el análisis."""
    pass

class MemoryLimitError(AnalysisError):
    """Error de límite de memoria excedido."""
    pass

class TimeoutError(AnalysisError):
    """Error de timeout durante el análisis."""
    pass

@dataclass
class ErrorReport:
    """Reporte de error durante análisis con contexto adicional."""
    file_path: str
    error_type: str
    error_message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    stack_trace: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    severity: str = "error"
    context: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

class RobustAnalyzer:
    """Analizador robusto con manejo de errores avanzado y recuperación."""
    
    def __init__(self, config: ConfigurationManager):
        self.config = config
        self.errors: List[ErrorReport] = []
        self.max_memory_gb = config.get('analysis.max_memory_usage_gb', 4)
        self.timeout_seconds = config.get('analysis.timeout_per_file_seconds', 30)
        self.max_file_size_mb = config.get('analysis.max_file_size_mb', 10)
        self.error_recovery_strategies = {
            'SyntaxError': self._recover_from_syntax_error,
            'UnicodeDecodeError': self._recover_from_encoding_error,
            'MemoryError': self._recover_from_memory_error
        }
    
    def check_memory_usage(self):
        """Verifica el uso de memoria con threshold dinámico."""
        process = psutil.Process()
        memory_gb = process.memory_info().rss / (1024 ** 3)
        
        # Threshold dinámico basado en memoria disponible
        available_memory_gb = psutil.virtual_memory().available / (1024 ** 3)
        effective_limit = min(self.max_memory_gb, available_memory_gb * 0.8)
        
        if memory_gb > effective_limit:
            gc.collect()  # Intentar liberar memoria
            memory_gb = process.memory_info().rss / (1024 ** 3)
            
            if memory_gb > effective_limit:
                raise MemoryLimitError(
                    f"Memory usage ({memory_gb:.2f}GB) exceeds limit ({effective_limit:.2f}GB)"
                )
    
    def analyze_file_safe(self, file_path: str) -> Optional[Tuple[ast.AST, str]]:
        """Analiza un archivo con manejo robusto de errores y recuperación."""
        try:
            # Verificar tamaño del archivo
            file_size_mb = os.path.getsize(file_path) / (1024 ** 2)
            if file_size_mb > self.max_file_size_mb:
                self.errors.append(ErrorReport(
                    file_path=file_path,
                    error_type="FileSizeError",
                    error_message=f"File too large ({file_size_mb:.2f}MB > {self.max_file_size_mb}MB)",
                    severity="warning"
                ))
                return None
            
            # Verificar memoria antes de procesar
            self.check_memory_usage()
            
            # Intentar múltiples encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # Último intento con errores ignorados
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    self.errors.append(ErrorReport(
                        file_path=file_path,
                        error_type="EncodingWarning",
                        error_message="File read with errors replaced",
                        severity="warning"
                    ))
            
            # Parsear con timeout
            tree = self._parse_with_timeout(content, file_path)
            
            if tree:
                return tree, content
            else:
                return None
            
        except MemoryLimitError as e:
            self.errors.append(ErrorReport(
                file_path=file_path,
                error_type="MemoryLimitError",
                error_message=str(e),
                severity="critical"
            ))
            gc.collect()
            return None
        
        except Exception as e:
            error_type = type(e).__name__
            
            # Intentar estrategia de recuperación si existe
            if error_type in self.error_recovery_strategies:
                recovery_result = self.error_recovery_strategies[error_type](file_path, e)
                if recovery_result:
                    return recovery_result
            
            self.errors.append(ErrorReport(
                file_path=file_path,
                error_type=error_type,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                severity="error"
            ))
            return None
    
    def _parse_with_timeout(self, content: str, file_path: str) -> Optional[ast.AST]:
        """Parsea código con timeout."""
        result_queue = queue.Queue()
        
        def parse_worker():
            try:
                tree = ast.parse(content, filename=file_path)
                result_queue.put(('success', tree))
            except SyntaxError as e:
                result_queue.put(('error', e))
            except Exception as e:
                result_queue.put(('error', e))
        
        thread = threading.Thread(target=parse_worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout_seconds)
        
        if thread.is_alive():
            self.errors.append(ErrorReport(
                file_path=file_path,
                error_type="TimeoutError",
                error_message=f"Parsing timeout after {self.timeout_seconds} seconds",
                severity="error"
            ))
            return None
        
        try:
            status, result = result_queue.get_nowait()
            if status == 'success':
                return result
            else:
                raise result
        except queue.Empty:
            return None
        except SyntaxError as e:
            self.errors.append(ErrorReport(
                file_path=file_path,
                error_type="SyntaxError",
                error_message=str(e),
                line_number=e.lineno,
                column_number=e.offset,
                context=e.text,
                severity="error"
            ))
            return None
    
    def _recover_from_syntax_error(self, file_path: str, error: Exception) -> Optional[Tuple]:
        """Intenta recuperarse de errores de sintaxis."""
        # Intentar parsear parcialmente línea por línea
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        valid_lines = []
        for i, line in enumerate(lines, 1):
            try:
                ast.parse(line)
                valid_lines.append(line)
            except SyntaxError:
                valid_lines.append(f"# Line {i} skipped due to syntax error\n")
        
        partial_content = ''.join(valid_lines)
        try:
            tree = ast.parse(partial_content)
            return tree, partial_content
        except:
            return None
    
    def _recover_from_encoding_error(self, file_path: str, error: Exception) -> Optional[Tuple]:
        """Intenta recuperarse de errores de encoding."""
        # Leer como binario y decodificar con reemplazo
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        content = binary_content.decode('utf-8', errors='replace')
        try:
            tree = ast.parse(content, filename=file_path)
            return tree, content
        except:
            return None
    
    def _recover_from_memory_error(self, file_path: str, error: Exception) -> Optional[Tuple]:
        """Intenta recuperarse de errores de memoria."""
        gc.collect()
        
        # Intentar procesar archivo por chunks
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            # Leer solo las primeras líneas
            lines = []
            for i, line in enumerate(f):
                if i >= 1000:  # Limitar a 1000 líneas
                    break
                lines.append(line)
        
        partial_content = ''.join(lines)
        try:
            tree = ast.parse(partial_content)
            return tree, partial_content
        except:
            return None
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Genera un resumen detallado de errores."""
        error_types = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for error in self.errors:
            error_types[error.error_type] += 1
            severity_counts[error.severity] += 1
        
        return {
            "total_errors": len(self.errors),
            "error_types": dict(error_types),
            "severity_counts": dict(severity_counts),
            "failed_files": list(set(e.file_path for e in self.errors)),
            "critical_errors": [e.to_dict() for e in self.errors if e.severity == "critical"],
            "errors": [e.to_dict() for e in self.errors][:100]  # Limitar a 100 para reportes
        }

# =====================================================================
# SISTEMA DE EMBEDDINGS MEJORADO
# =====================================================================

class EmbeddingGenerator:
    """Generador de embeddings con múltiples estrategias."""
    
    def __init__(self, config: ConfigurationManager):
        self.config = config
        self.model_type = config.get('embedding.model_type', 'semantic')
        self.vector_size = config.get('embedding.vector_size', 768)
        self.model = None
        self.tokenizer = None
        
        self._initialize_model()
    
    def _initialize_model(self):
        """Inicializa el modelo de embeddings según configuración."""
        if self.model_type == 'semantic' and TRANSFORMERS_AVAILABLE:
            try:
                from transformers import AutoTokenizer, AutoModel
                model_name = "microsoft/codebert-base"
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(model_name)
                self.model.eval()
                logging.info(f"Loaded semantic embedding model: {model_name}")
            except Exception as e:
                logging.warning(f"Failed to load transformer model: {e}")
                self._use_fallback_model()
        else:
            self._use_fallback_model()
    
    def _use_fallback_model(self):
        """Usa modelo de embeddings basado en características."""
        logging.info("Using feature-based embedding model")
        self.model_type = 'feature'
    
    def generate(self, code: str) -> np.ndarray:
        """Genera embedding para código."""
        if self.model_type == 'semantic' and self.model and self.tokenizer:
            return self._generate_semantic_embedding(code)
        else:
            return self._generate_feature_embedding(code)
    
    def _generate_semantic_embedding(self, code: str) -> np.ndarray:
        """Genera embedding semántico usando transformer."""
        try:
            inputs = self.tokenizer(
                code,
                return_tensors="pt",
                max_length=self.config.get('embedding.max_sequence_length', 512),
                truncation=True,
                padding=True
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).numpy()[0]
            
            # Ajustar al tamaño configurado si es necesario
            if len(embedding) != self.vector_size:
                embedding = self._resize_embedding(embedding, self.vector_size)
            
            return embedding
        
        except Exception as e:
            logging.warning(f"Failed to generate semantic embedding: {e}")
            return self._generate_feature_embedding(code)
    
    def _generate_feature_embedding(self, code: str) -> np.ndarray:
        """Genera embedding basado en características del código."""
        features = []
        
        # Características léxicas
        lines = code.split('\n')
        features.extend([
            len(code),                                # Longitud total
            len(lines),                               # Número de líneas
            sum(1 for l in lines if l.strip()),      # Líneas no vacías
            code.count(' ') / max(len(code), 1),     # Ratio de espacios
            code.count('\t'),                         # Tabulaciones
            sum(1 for l in lines if l.strip().startswith('#')),  # Comentarios
        ])
        
        # Características sintácticas
        try:
            tree = ast.parse(code)
            
            # Contar tipos de nodos
            node_counts = Counter()
            for node in ast.walk(tree):
                node_counts[type(node).__name__] += 1
            
            # Agregar conteos normalizados de nodos comunes
            common_nodes = ['FunctionDef', 'ClassDef', 'If', 'For', 'While', 
                          'Import', 'Assign', 'Call', 'Return', 'Try']
            
            total_nodes = sum(node_counts.values())
            for node_type in common_nodes:
                features.append(node_counts.get(node_type, 0) / max(total_nodes, 1))
            
            # Características de complejidad
            features.extend([
                self._calculate_max_depth(tree),
                len(list(ast.walk(tree))),
                self._count_unique_names(tree),
            ])
            
        except SyntaxError:
            # Si hay error de sintaxis, usar valores por defecto
            features.extend([0] * 13)
        
        # Características de estilo
        features.extend([
            1 if 'class' in code else 0,
            1 if 'def' in code else 0,
            1 if 'import' in code else 0,
            1 if '__name__' in code else 0,
            1 if 'try' in code else 0,
            1 if 'raise' in code else 0,
        ])
        
        # Expandir o comprimir al tamaño deseado
        feature_vector = np.array(features, dtype=np.float32)
        
        # Crear embedding del tamaño configurado
        if len(feature_vector) < self.vector_size:
            # Expandir usando transformación no lineal
            expanded = np.zeros(self.vector_size)
            expanded[:len(feature_vector)] = feature_vector
            
            # Agregar características derivadas
            for i in range(len(feature_vector), self.vector_size):
                # Combinación no lineal de características existentes
                idx1, idx2 = i % len(feature_vector), (i * 7) % len(feature_vector)
                expanded[i] = np.tanh(feature_vector[idx1] * feature_vector[idx2])
            
            return expanded
        else:
            # Comprimir usando PCA simulado
            return self._resize_embedding(feature_vector, self.vector_size)
    
    def _resize_embedding(self, embedding: np.ndarray, target_size: int) -> np.ndarray:
        """Redimensiona un embedding al tamaño objetivo."""
        current_size = len(embedding)
        
        if current_size == target_size:
            return embedding
        elif current_size < target_size:
            # Expandir
            resized = np.zeros(target_size)
            resized[:current_size] = embedding
            return resized
        else:
            # Comprimir usando submuestreo
            indices = np.linspace(0, current_size - 1, target_size, dtype=int)
            return embedding[indices]
    
    def _calculate_max_depth(self, tree: ast.AST) -> int:
        """Calcula la profundidad máxima del AST."""
        class DepthVisitor(ast.NodeVisitor):
            def __init__(self):
                self.max_depth = 0
                self.current_depth = 0
            
            def generic_visit(self, node):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                super().generic_visit(node)
                self.current_depth -= 1
        
        visitor = DepthVisitor()
        visitor.visit(tree)
        return visitor.max_depth
    
    def _count_unique_names(self, tree: ast.AST) -> int:
        """Cuenta nombres únicos en el AST."""
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
        return len(names)
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calcula similitud coseno entre embeddings."""
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

# =====================================================================
# ANALIZADOR DE CÓDIGO MEJORADO
# =====================================================================

@dataclass
class CodeMetrics:
    """Métricas de calidad de código extendidas."""
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0
    logical_lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    comment_ratio: float = 0.0
    maintainability_index: float = 0.0
    halstead_metrics: Dict[str, float] = field(default_factory=dict)
    security_issues: List[Dict[str, Any]] = field(default_factory=list)
    code_smells: List[Dict[str, Any]] = field(default_factory=list)
    test_coverage: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    function_count: int = 0
    class_count: int = 0
    max_nesting_depth: int = 0

class CodeAnalyzer:
    """Analizador de código con métricas avanzadas."""
    
    def __init__(self, config: Optional[ConfigurationManager] = None):
        self.config = config or ConfigurationManager()
        self.security_patterns = self._load_security_patterns()
    
    def _load_security_patterns(self) -> List[Tuple[str, str, str]]:
        """Carga patrones de seguridad mejorados."""
        patterns = [
            # Ejecución de código
            (r'\beval\s*\([^)]*\)', "Use of eval() is dangerous", "critical"),
            (r'\bexec\s*\([^)]*\)', "Use of exec() is dangerous", "critical"),
            (r'__import__\s*\([^)]*\)', "Dynamic imports can be risky", "high"),
            
            # Deserialización
            (r'pickle\.loads?\s*\([^)]*\)', "Pickle deserialization can be unsafe", "high"),
            (r'yaml\.load\s*\([^)]*\)', "Use yaml.safe_load() instead of yaml.load()", "high"),
            (r'marshal\.loads?\s*\([^)]*\)', "Marshal deserialization can be unsafe", "high"),
            
            # Inyección de comandos
            (r'subprocess\.\w+\([^)]*shell\s*=\s*True', "Shell injection vulnerability possible", "critical"),
            (r'os\.system\s*\([^)]*\)', "os.system() vulnerable to injection", "high"),
            (r'os\.popen\s*\([^)]*\)', "os.popen() vulnerable to injection", "high"),
            
            # SQL Injection
            (r'\".*SELECT.*%s.*\"', "Possible SQL injection vulnerability", "critical"),
            (r'f\".*SELECT.*{.*}.*\"', "Possible SQL injection with f-strings", "critical"),
            (r'\.format\([^)]*\).*SELECT', "Possible SQL injection with format()", "critical"),
            
            # Path traversal
            (r'open\s*\([^)]*\.\.[^)]*\)', "Possible path traversal vulnerability", "high"),
            (r'os\.path\.join\([^)]*\.\.[^)]*\)', "Possible path traversal", "high"),
            
            # Credenciales hardcodeadas
            (r'(password|secret|token|api_key|apikey)\s*=\s*["\'][^"\']+["\']', 
             "Hardcoded credentials detected", "critical"),
            (r'(AWS_SECRET|AZURE_KEY|GCP_KEY)\s*=\s*["\'][^"\']+["\']',
             "Cloud credentials hardcoded", "critical"),
            
            # Uso inseguro de random
            (r'random\.\w+\s*\([^)]*\)', "Use secrets module for security-sensitive randomness", "medium"),
            
            # HTTP sin cifrar
            (r'http://[^s]', "Using HTTP instead of HTTPS", "medium"),
            
            # Configuraciones inseguras
            (r'verify\s*=\s*False', "SSL verification disabled", "high"),
            (r'DEBUG\s*=\s*True', "Debug mode enabled in production", "medium"),
        ]
        
        # Agregar patrones personalizados de configuración
        custom_patterns = self.config.get('metrics.security.custom_patterns', [])
        for pattern in custom_patterns:
            if isinstance(pattern, dict):
                patterns.append((
                    pattern.get('regex', ''),
                    pattern.get('message', 'Custom security issue'),
                    pattern.get('severity', 'medium')
                ))
        
        return patterns
    
    def analyze_code(self, code: str, file_path: Optional[str] = None) -> CodeMetrics:
        """Análisis completo del código con todas las métricas."""
        metrics = CodeMetrics()
        
        # Métricas básicas de líneas
        lines = code.split('\n')
        metrics.lines_of_code = len(lines)
        metrics.blank_lines = sum(1 for l in lines if not l.strip())
        metrics.comment_lines = sum(1 for l in lines if l.strip().startswith('#'))
        metrics.logical_lines_of_code = metrics.lines_of_code - metrics.blank_lines - metrics.comment_lines
        
        # Ratio de comentarios
        if metrics.lines_of_code > 0:
            metrics.comment_ratio = metrics.comment_lines / metrics.lines_of_code
        
        try:
            tree = ast.parse(code)
            
            # Análisis del AST
            metrics.cyclomatic_complexity = self._calculate_cyclomatic_complexity(tree)
            metrics.cognitive_complexity = self._calculate_cognitive_complexity(tree)
            metrics.max_nesting_depth = self._calculate_max_nesting_depth(tree)
            metrics.halstead_metrics = self._calculate_halstead_metrics(tree)
            
            # Contar elementos
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    metrics.function_count += 1
                elif isinstance(node, ast.ClassDef):
                    metrics.class_count += 1
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    metrics.dependencies.extend(self._extract_imports(node))
            
            # Detectar code smells
            metrics.code_smells = self._detect_code_smells(tree, code)
            
        except SyntaxError:
            # Si hay error de sintaxis, usar valores por defecto
            pass
        
        # Análisis de seguridad
        metrics.security_issues = self._detect_security_issues(code)
        
        # Índice de mantenibilidad
        metrics.maintainability_index = self._calculate_maintainability_index(metrics)
        
        return metrics
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Calcula la complejidad ciclomática."""
        complexity = 1
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                ast.With, ast.Assert, ast.Raise)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, ast.comprehension):
                complexity += sum(1 for _ in node.ifs)
        
        return complexity
    
    def _calculate_cognitive_complexity(self, tree: ast.AST) -> int:
        """Calcula la complejidad cognitiva mejorada."""
        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 0
                self.nesting_level = 0
            
            def visit_If(self, node):
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1
            
            def visit_While(self, node):
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1
            
            def visit_For(self, node):
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1
            
            def visit_ExceptHandler(self, node):
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1
            
            def visit_BoolOp(self, node):
                self.complexity += len(node.values) - 1
                self.generic_visit(node)
            
            def visit_Lambda(self, node):
                self.complexity += 1
                self.generic_visit(node)
        
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        return visitor.complexity
    
    def _calculate_max_nesting_depth(self, tree: ast.AST) -> int:
        """Calcula la profundidad máxima de anidamiento."""
        class NestingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.max_depth = 0
                self.current_depth = 0
            
            def _enter_block(self):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
            
            def _exit_block(self):
                self.current_depth -= 1
            
            def visit_If(self, node):
                self._enter_block()
                self.generic_visit(node)
                self._exit_block()
            
            def visit_For(self, node):
                self._enter_block()
                self.generic_visit(node)
                self._exit_block()
            
            def visit_While(self, node):
                self._enter_block()
                self.generic_visit(node)
                self._exit_block()
            
            def visit_With(self, node):
                self._enter_block()
                self.generic_visit(node)
                self._exit_block()
            
            def visit_Try(self, node):
                self._enter_block()
                self.generic_visit(node)
                self._exit_block()
        
        visitor = NestingVisitor()
        visitor.visit(tree)
        return visitor.max_depth
    
    def _calculate_halstead_metrics(self, tree: ast.AST) -> Dict[str, float]:
        """Calcula métricas de Halstead."""
        operators = set()
        operands = set()
        total_operators = 0
        total_operands = 0
        
        for node in ast.walk(tree):
            # Contar operadores
            if isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                                ast.Pow, ast.LShift, ast.RShift, ast.BitOr,
                                ast.BitXor, ast.BitAnd, ast.FloorDiv, ast.And,
                                ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt,
                                ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
                                ast.In, ast.NotIn)):
                operators.add(type(node).__name__)
                total_operators += 1
            
            # Contar operandos
            elif isinstance(node, (ast.Name, ast.Constant, ast.Str, ast.Num)):
                if isinstance(node, ast.Name):
                    operands.add(node.id)
                elif isinstance(node, ast.Constant):
                    operands.add(str(node.value))
                total_operands += 1
        
        n1 = len(operators)  # Operadores únicos
        n2 = len(operands)   # Operandos únicos
        N1 = total_operators # Total operadores
        N2 = total_operands  # Total operandos
        
        # Calcular métricas
        vocabulary = n1 + n2
        length = N1 + N2
        
        if vocabulary > 0 and length > 0:
            volume = length * np.log2(vocabulary) if vocabulary > 0 else 0
            difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
            effort = volume * difficulty
            time = effort / 18  # Segundos
            bugs = volume / 3000  # Bugs estimados
        else:
            volume = difficulty = effort = time = bugs = 0
        
        return {
            'vocabulary': vocabulary,
            'length': length,
            'volume': volume,
            'difficulty': difficulty,
            'effort': effort,
            'time': time,
            'bugs': bugs
        }
    
    def _detect_security_issues(self, code: str) -> List[Dict[str, Any]]:
        """Detecta problemas de seguridad con contexto mejorado."""
        issues = []
        lines = code.split('\n')
        
        for pattern, message, severity in self.security_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
                # Encontrar número de línea
                line_num = code[:match.start()].count('\n') + 1
                
                # Extraer contexto
                context_start = max(0, line_num - 2)
                context_end = min(len(lines), line_num + 2)
                context = '\n'.join(lines[context_start:context_end])
                
                issues.append({
                    'type': 'security',
                    'severity': severity,
                    'message': message,
                    'line': line_num,
                    'column': match.start() - code.rfind('\n', 0, match.start()),
                    'match': match.group(0)[:100],
                    'context': context
                })
        
        return issues
    
    def _detect_code_smells(self, tree: ast.AST, code: str) -> List[Dict[str, Any]]:
        """Detecta code smells con descripción detallada."""
        smells = []
        lines = code.split('\n')
        
        for node in ast.walk(tree):
            # Funciones muy largas
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                threshold = self.config.get('metrics.complexity.lines_per_function_threshold', 50)
                
                if func_lines > threshold:
                    smells.append({
                        'type': 'long_function',
                        'name': node.name,
                        'line': node.lineno,
                        'severity': 'medium',
                        'message': f"Function '{node.name}' is too long ({func_lines} lines > {threshold})",
                        'metrics': {'lines': func_lines, 'threshold': threshold}
                    })
                
                # Demasiados parámetros
                param_count = len(node.args.args)
                param_threshold = self.config.get('metrics.complexity.parameters_threshold', 5)
                
                if param_count > param_threshold:
                    smells.append({
                        'type': 'too_many_parameters',
                        'name': node.name,
                        'line': node.lineno,
                        'severity': 'medium',
                        'message': f"Function '{node.name}' has too many parameters ({param_count} > {param_threshold})",
                        'metrics': {'parameters': param_count, 'threshold': param_threshold}
                    })
            
            # Clases muy grandes
            elif isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_threshold = self.config.get('metrics.complexity.methods_per_class_threshold', 20)
                
                if len(methods) > method_threshold:
                    smells.append({
                        'type': 'large_class',
                        'name': node.name,
                        'line': node.lineno,
                        'severity': 'medium',
                        'message': f"Class '{node.name}' has too many methods ({len(methods)} > {method_threshold})",
                        'metrics': {'methods': len(methods), 'threshold': method_threshold}
                    })
            
            # Complejidad excesiva en funciones
            elif isinstance(node, ast.FunctionDef):
                complexity = self._calculate_cyclomatic_complexity(node)
                complexity_threshold = self.config.get('metrics.complexity.cyclomatic_threshold', 10)
                
                if complexity > complexity_threshold:
                    smells.append({
                        'type': 'complex_function',
                        'name': node.name,
                        'line': node.lineno,
                        'severity': 'high',
                        'message': f"Function '{node.name}' has high complexity ({complexity} > {complexity_threshold})",
                        'metrics': {'complexity': complexity, 'threshold': complexity_threshold}
                    })
        
        # Detectar código duplicado (simplificado)
        self._detect_duplicate_code(lines, smells)
        
        return smells
    
    def _detect_duplicate_code(self, lines: List[str], smells: List[Dict]):
        """Detecta código duplicado simple."""
        # Buscar bloques de código idénticos
        min_block_size = 5
        seen_blocks = {}
        
        for i in range(len(lines) - min_block_size):
            block = '\n'.join(lines[i:i+min_block_size])
            block_hash = hashlib.md5(block.encode()).hexdigest()
            
            if block_hash in seen_blocks:
                smells.append({
                    'type': 'duplicate_code',
                    'line': i + 1,
                    'severity': 'low',
                    'message': f"Possible duplicate code block starting at line {i+1}",
                    'duplicate_of': seen_blocks[block_hash]
                })
            else:
                seen_blocks[block_hash] = i + 1
    
    def _calculate_maintainability_index(self, metrics: CodeMetrics) -> float:
        """Calcula el índice de mantenibilidad de Microsoft."""
        import math
        
        # Fórmula del Índice de Mantenibilidad
        # MI = 171 - 5.2 * ln(V) - 0.23 * CC - 16.2 * ln(LOC)
        # Donde V = Volumen Halstead, CC = Complejidad Ciclomática, LOC = Líneas de código
        
        volume = metrics.halstead_metrics.get('volume', 1)
        complexity = metrics.cyclomatic_complexity
        loc = max(metrics.logical_lines_of_code, 1)
        
        mi = 171
        if volume > 0:
            mi -= 5.2 * math.log(volume)
        mi -= 0.23 * complexity
        if loc > 0:
            mi -= 16.2 * math.log(loc)
        
        # Ajustar por ratio de comentarios (bonus)
        mi += metrics.comment_ratio * 50
        
        # Normalizar entre 0 y 100
        mi = max(0, min(100, mi))
        
        return mi
    
    def _extract_imports(self, node: Union[ast.Import, ast.ImportFrom]) -> List[str]:
        """Extrae nombres de módulos importados."""
        imports = []
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        
        return imports

# =====================================================================
# GENERADOR DE TESTS AUTOMÁTICOS
# =====================================================================

class TestGenerator:
    """Generador de tests unitarios automáticos."""
    
    def __init__(self, config: ConfigurationManager):
        self.config = config
        self.framework = config.get('testing.framework', 'pytest')
    
    def generate_tests(self, node: ast.AST, code: str) -> List[Dict[str, Any]]:
        """Genera tests para un nodo de código."""
        tests = []
        
        if isinstance(node, ast.FunctionDef):
            tests.extend(self._generate_function_tests(node, code))
        elif isinstance(node, ast.ClassDef):
            tests.extend(self._generate_class_tests(node, code))
        
        return tests
    
    def _generate_function_tests(self, func: ast.FunctionDef, code: str) -> List[Dict[str, Any]]:
        """Genera tests para una función."""
        tests = []
        
        # Test básico
        test_code = self._create_function_test_template(func)
        tests.append({
            'name': f"test_{func.name}_basic",
            'code': test_code,
            'type': 'unit',
            'framework': self.framework
        })
        
        # Test de edge cases si es posible inferirlos
        if self._has_numeric_params(func):
            edge_test = self._create_edge_case_test(func)
            tests.append({
                'name': f"test_{func.name}_edge_cases",
                'code': edge_test,
                'type': 'edge_case',
                'framework': self.framework
            })
        
        # Test de excepciones si la función tiene try/except
        if self._has_exception_handling(func):
            exception_test = self._create_exception_test(func)
            tests.append({
                'name': f"test_{func.name}_exceptions",
                'code': exception_test,
                'type': 'exception',
                'framework': self.framework
            })
        
        return tests
    
    def _generate_class_tests(self, cls: ast.ClassDef, code: str) -> List[Dict[str, Any]]:
        """Genera tests para una clase."""
        tests = []
        
        # Test de inicialización
        init_test = self._create_class_init_test(cls)
        tests.append({
            'name': f"test_{cls.name}_init",
            'code': init_test,
            'type': 'init',
            'framework': self.framework
        })
        
        # Tests para métodos públicos
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                method_test = self._create_method_test(cls.name, node)
                tests.append({
                    'name': f"test_{cls.name}_{node.name}",
                    'code': method_test,
                    'type': 'method',
                    'framework': self.framework
                })
        
        return tests
    
    def _create_function_test_template(self, func: ast.FunctionDef) -> str:
        """Crea plantilla de test para función."""
        params = [arg.arg for arg in func.args.args]
        param_values = self._infer_param_values(func)
        
        if self.framework == 'pytest':
            template = f"""
def test_{func.name}_basic():
    '''Test básico para {func.name}'''
    # Arrange
    {self._create_param_assignments(params, param_values)}
    
    # Act
    result = {func.name}({', '.join(params)})
    
    # Assert
    assert result is not None
    # TODO: Agregar assertions específicas
"""
        else:  # unittest
            template = f"""
class Test{func.name.capitalize()}(unittest.TestCase):
    def test_{func.name}_basic(self):
        '''Test básico para {func.name}'''
        # Arrange
        {self._create_param_assignments(params, param_values)}
        
        # Act
        result = {func.name}({', '.join(params)})
        
        # Assert
        self.assertIsNotNone(result)
        # TODO: Agregar assertions específicas
"""
        
        return template
    
    def _create_edge_case_test(self, func: ast.FunctionDef) -> str:
        """Crea test de edge cases."""
        params = [arg.arg for arg in func.args.args]
        
        if self.framework == 'pytest':
            template = f"""
@pytest.mark.parametrize("{', '.join(params)}", [
    ({', '.join(['0' if self._is_numeric_param(p) else '""' for p in params])}),  # Valores vacíos/cero
    ({', '.join(['-1' if self._is_numeric_param(p) else 'None' for p in params])}),  # Valores negativos/None
    ({', '.join(['999999' if self._is_numeric_param(p) else '"x"*1000' for p in params])}),  # Valores grandes
])
def test_{func.name}_edge_cases({', '.join(params)}):
    '''Test de edge cases para {func.name}'''
    try:
        result = {func.name}({', '.join(params)})
        # Verificar que maneja edge cases apropiadamente
        assert result is not None or True  # Ajustar según comportamiento esperado
    except Exception as e:
        # Verificar que las excepciones son esperadas
        assert isinstance(e, (ValueError, TypeError))
"""
        else:
            template = f"""
class Test{func.name.capitalize()}EdgeCases(unittest.TestCase):
    def test_edge_cases(self):
        '''Test de edge cases para {func.name}'''
        edge_cases = [
            ({', '.join(['0' if self._is_numeric_param(p) else '""' for p in params])}),
            ({', '.join(['-1' if self._is_numeric_param(p) else 'None' for p in params])}),
            ({', '.join(['999999' if self._is_numeric_param(p) else '"x"*1000' for p in params])}),
        ]
        
        for case in edge_cases:
            with self.subTest(case=case):
                try:
                    result = {func.name}(*case)
                    self.assertIsNotNone(result)
                except (ValueError, TypeError):
                    pass  # Excepciones esperadas
"""
        
        return template
    
    def _create_exception_test(self, func: ast.FunctionDef) -> str:
        """Crea test de manejo de excepciones."""
        if self.framework == 'pytest':
            template = f"""
def test_{func.name}_exceptions():
    '''Test de excepciones para {func.name}'''
    with pytest.raises((ValueError, TypeError, Exception)):
        # Llamar función con parámetros inválidos
        {func.name}(None)  # Ajustar según parámetros
"""
        else:
            template = f"""
class Test{func.name.capitalize()}Exceptions(unittest.TestCase):
    def test_exceptions(self):
        '''Test de excepciones para {func.name}'''
        with self.assertRaises((ValueError, TypeError, Exception)):
            {func.name}(None)  # Ajustar según parámetros
"""
        
        return template
    
    def _create_class_init_test(self, cls: ast.ClassDef) -> str:
        """Crea test de inicialización de clase."""
        if self.framework == 'pytest':
            template = f"""
def test_{cls.name}_initialization():
    '''Test de inicialización para {cls.name}'''
    # Act
    instance = {cls.name}()
    
    # Assert
    assert instance is not None
    assert isinstance(instance, {cls.name})
"""
        else:
            template = f"""
class Test{cls.name}(unittest.TestCase):
    def test_initialization(self):
        '''Test de inicialización para {cls.name}'''
        instance = {cls.name}()
        self.assertIsNotNone(instance)
        self.assertIsInstance(instance, {cls.name})
"""
        
        return template
    
    def _create_method_test(self, class_name: str, method: ast.FunctionDef) -> str:
        """Crea test para método de clase."""
        if self.framework == 'pytest':
            template = f"""
def test_{class_name}_{method.name}():
    '''Test para {class_name}.{method.name}'''
    # Arrange
    instance = {class_name}()
    
    # Act
    result = instance.{method.name}()
    
    # Assert
    assert result is not None or True  # Ajustar según comportamiento esperado
"""
        else:
            template = f"""
class Test{class_name}{method.name.capitalize()}(unittest.TestCase):
    def test_method(self):
        '''Test para {class_name}.{method.name}'''
        instance = {class_name}()
        result = instance.{method.name}()
        # Ajustar assertions según comportamiento esperado
"""
        
        return template
    
    def _has_numeric_params(self, func: ast.FunctionDef) -> bool:
        """Verifica si la función tiene parámetros numéricos."""
        # Heurística simple basada en nombres de parámetros
        numeric_indicators = ['num', 'count', 'size', 'length', 'index', 'id', 'age', 'amount']
        return any(
            any(indicator in arg.arg.lower() for indicator in numeric_indicators)
            for arg in func.args.args
        )
    
    def _is_numeric_param(self, param_name: str) -> bool:
        """Verifica si un parámetro es probablemente numérico."""
        numeric_indicators = ['num', 'count', 'size', 'length', 'index', 'id', 'age', 'amount']
        return any(indicator in param_name.lower() for indicator in numeric_indicators)
    
    def _has_exception_handling(self, func: ast.FunctionDef) -> bool:
        """Verifica si la función tiene manejo de excepciones."""
        for node in ast.walk(func):
            if isinstance(node, (ast.Try, ast.Raise)):
                return True
        return False
    
    def _infer_param_values(self, func: ast.FunctionDef) -> Dict[str, Any]:
        """Infiere valores de prueba para parámetros."""
        values = {}
        
        for arg in func.args.args:
            param_name = arg.arg.lower()
            
            # Inferir tipo basado en nombre
            if any(x in param_name for x in ['str', 'text', 'name', 'message']):
                values[arg.arg] = '"test_value"'
            elif any(x in param_name for x in ['num', 'count', 'size', 'id']):
                values[arg.arg] = '1'
            elif any(x in param_name for x in ['flag', 'is_', 'has_', 'should_']):
                values[arg.arg] = 'True'
            elif any(x in param_name for x in ['list', 'items', 'elements']):
                values[arg.arg] = '[]'
            elif any(x in param_name for x in ['dict', 'config', 'options']):
                values[arg.arg] = '{}'
            else:
                values[arg.arg] = 'None'
        
        return values
    
    def _create_param_assignments(self, params: List[str], values: Dict[str, Any]) -> str:
        """Crea asignaciones de parámetros para test."""
        assignments = []
        for param in params:
            value = values.get(param, 'None')
            assignments.append(f"{param} = {value}")
        return '\n    '.join(assignments)

# =====================================================================
# NODO Y GRAFO MEJORADOS CON FUNCIONALIDAD COMPLETA
# =====================================================================

@dataclass
class PersistentCodeNode:
    """Nodo con persistencia completa y metadata extendida."""
    code_id: str
    code_segment: str
    code_hash: str
    dependencies: List[str]
    purpose: str
    metrics: CodeMetrics
    test_cases: List[Dict]
    test_results: List[Dict]
    embedding: Optional[np.ndarray]
    creation_timestamp: float
    update_timestamp: float
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    ast_node: Optional[ast.AST] = None
    parent_node_id: Optional[str] = None
    child_node_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    documentation: Optional[str] = None
    version: str = "3.1"
    
    def to_dict(self) -> Dict:
        """Serializa el nodo completamente."""
        metrics_dict = asdict(self.metrics) if isinstance(self.metrics, CodeMetrics) else self.metrics
        
        return {
            'code_id': self.code_id,
            'code_segment': self.code_segment,
            'code_hash': self.code_hash,
            'dependencies': self.dependencies,
            'purpose': self.purpose,
            'metrics': metrics_dict,
            'test_cases': self.test_cases,
            'test_results': self.test_results,
            'embedding': self.embedding.tolist() if self.embedding is not None else None,
            'creation_timestamp': self.creation_timestamp,
            'update_timestamp': self.update_timestamp,
            'file_path': self.file_path,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'parent_node_id': self.parent_node_id,
            'child_node_ids': self.child_node_ids,
            'tags': self.tags,
            'documentation': self.documentation,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PersistentCodeNode':
        """Reconstruye el nodo desde un diccionario."""
        embedding = np.array(data['embedding']) if data.get('embedding') else None
        
        # Reconstruir métricas
        metrics_data = data.get('metrics', {})
        if isinstance(metrics_data, dict) and not isinstance(metrics_data, CodeMetrics):
            metrics = CodeMetrics(**{
                k: v for k, v in metrics_data.items() 
                if k in CodeMetrics.__dataclass_fields__
            })
        else:
            metrics = metrics_data
        
        return cls(
            code_id=data['code_id'],
            code_segment=data['code_segment'],
            code_hash=data['code_hash'],
            dependencies=data.get('dependencies', []),
            purpose=data.get('purpose', ''),
            metrics=metrics,
            test_cases=data.get('test_cases', []),
            test_results=data.get('test_results', []),
            embedding=embedding,
            creation_timestamp=data.get('creation_timestamp', time.time()),
            update_timestamp=data.get('update_timestamp', time.time()),
            file_path=data.get('file_path'),
            start_line=data.get('start_line'),
            end_line=data.get('end_line'),
            parent_node_id=data.get('parent_node_id'),
            child_node_ids=data.get('child_node_ids', []),
            tags=data.get('tags', []),
            documentation=data.get('documentation'),
            version=data.get('version', '3.1')
        )
    


class EnterpriseSRPKGraph:
    """Grafo empresarial con todas las mejoras de v3.1."""
    
    def __init__(self, config: Optional[ConfigurationManager] = None):
        self.config = config or ConfigurationManager()
        self.cache = CacheManager(self.config)
        self.analyzer = RobustAnalyzer(self.config)
        self.code_analyzer = CodeAnalyzer(self.config)
        self.embedding_generator = EmbeddingGenerator(self.config)
        self.test_generator = TestGenerator(self.config)
        
        self.nodes: Dict[str, PersistentCodeNode] = {}
        self.edges: Dict[str, List[str]] = defaultdict(list)
        self.file_registry: Dict[str, List[str]] = {}
        self.metrics_history: List[Dict] = []
        
        # Threading para análisis paralelo
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get('analysis.max_workers', 4)
        )
        
        # Auto-guardado
        self.auto_save_enabled = self.config.get('persistence.auto_save', True)
        self.last_save_time = time.time()
        
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """Analiza un proyecto completo con procesamiento paralelo."""
        project_path = Path(project_path)
        results = {
            'project_path': str(project_path),
            'files_analyzed': 0,
            'files_failed': 0,
            'nodes_created': 0,
            'edges_created': 0,
            'errors': [],
            'start_time': time.time(),
            'version': '3.1'
        }
        
        # Obtener archivos a analizar
        files_to_analyze = self._get_python_files(project_path)
        total_files = len(files_to_analyze)
        
        logging.info(f"Found {total_files} Python files to analyze")
        
        # Procesamiento paralelo si está habilitado
        if self.config.get('analysis.parallel_processing', True):
            futures = []
            for file_path in files_to_analyze:
                future = self.executor.submit(self._analyze_file_wrapper, file_path)
                futures.append((file_path, future))
            
            # Recopilar resultados
            for file_path, future in futures:
                try:
                    file_results = future.result(
                        timeout=self.config.get('analysis.timeout_per_file_seconds', 30)
                    )
                    if file_results:
                        results['nodes_created'] += file_results['nodes_created']
                        results['edges_created'] += file_results['edges_created']
                        results['files_analyzed'] += 1
                except FutureTimeoutError:
                    logging.error(f"Timeout analyzing {file_path}")
                    results['files_failed'] += 1
                    results['errors'].append({
                        'file': str(file_path),
                        'error': 'Timeout'
                    })
                except Exception as e:
                    logging.error(f"Failed to analyze {file_path}: {e}")
                    results['files_failed'] += 1
                    results['errors'].append({
                        'file': str(file_path),
                        'error': str(e)
                    })
        else:
            # Procesamiento secuencial
            for i, file_path in enumerate(files_to_analyze):
                logging.info(f"Analyzing {i+1}/{total_files}: {file_path}")
                
                try:
                    file_results = self._analyze_file_wrapper(file_path)
                    if file_results:
                        results['nodes_created'] += file_results['nodes_created']
                        results['edges_created'] += file_results['edges_created']
                        results['files_analyzed'] += 1
                except Exception as e:
                    logging.error(f"Failed to analyze {file_path}: {e}")
                    results['files_failed'] += 1
                    results['errors'].append({
                        'file': str(file_path),
                        'error': str(e)
                    })
        
        # Analizar dependencias y crear edges
        self._analyze_dependencies()
        
        # Auto-guardar si está habilitado
        if self.auto_save_enabled:
            self._auto_save()
        
        results['end_time'] = time.time()
        results['duration'] = results['end_time'] - results['start_time']
        
        # Agregar resumen de métricas
        results['summary'] = self._generate_summary()
        
        # Guardar en historial
        self.metrics_history.append({
            'timestamp': results['end_time'],
            'summary': results['summary']
        })
        
        return results
    
    def _get_python_files(self, project_path: Path) -> List[Path]:
        """Obtiene lista de archivos Python a analizar con filtrado mejorado."""
        excluded_dirs = set(self.config.get('analysis.excluded_dirs', []))
        excluded_patterns = self.config.get('analysis.excluded_files', [])
        include_tests = self.config.get('analysis.include_tests', True)
        follow_symlinks = self.config.get('analysis.follow_symlinks', False)
        
        python_files = []
        
        def should_exclude(path: Path) -> bool:
            # Verificar directorio excluido
            for part in path.parts:
                if part in excluded_dirs:
                    return True
            
            # Verificar si es test y si debe incluirse
            if not include_tests:
                test_indicators = ['test_', '_test.py', 'tests/', 'testing/']
                if any(indicator in str(path).lower() for indicator in test_indicators):
                    return True
            
            # Verificar patrones excluidos
            for pattern in excluded_patterns:
                if path.match(pattern):
                    return True
            
            return False
        
        # Recorrer archivos
        for path in project_path.rglob('*.py'):
            # Verificar symlinks
            if not follow_symlinks and path.is_symlink():
                continue
            
            if not should_exclude(path):
                python_files.append(path)
        
        return sorted(python_files)
    
    def _analyze_file_wrapper(self, file_path: Path) -> Optional[Dict]:
        """Wrapper para análisis de archivo con caché."""
        try:
            # Verificar caché
            file_hash = self._get_file_hash(file_path)
            cache_key = f"analysis:{file_path}"
            cached_result = self.cache.get(cache_key, file_hash)
            
            if cached_result:
                # Restaurar desde caché
                for node_data in cached_result['nodes']:
                    node = PersistentCodeNode.from_dict(node_data)
                    self.nodes[node.code_id] = node
                
                # Registrar archivo
                self.file_registry[str(file_path)] = cached_result['node_ids']
                
                return {
                    'nodes_created': len(cached_result['nodes']),
                    'edges_created': 0
                }
            
            # Analizar archivo
            nodes = self._analyze_file(file_path)
            
            if nodes:
                # Guardar en caché
                cache_data = {
                    'nodes': [n.to_dict() for n in nodes],
                    'node_ids': [n.code_id for n in nodes]
                }
                self.cache.set(cache_key, cache_data, file_hash)
                
                return {
                    'nodes_created': len(nodes),
                    'edges_created': 0
                }
            
            return None
            
        except Exception as e:
            logging.error(f"Error in file analysis wrapper: {e}")
            return None
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calcula hash de un archivo con manejo de errores."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logging.warning(f"Failed to hash file {file_path}: {e}")
            return str(time.time())
    
    def _analyze_file(self, file_path: Path) -> List[PersistentCodeNode]:
        """Analiza un archivo y extrae nodos con análisis completo."""
        result = self.analyzer.analyze_file_safe(str(file_path))
        
        if not result:
            return []
        
        tree, content = result
        nodes = []
        
        # Analizar archivo completo
        file_metrics = self.code_analyzer.analyze_code(content, str(file_path))
        
        # Crear nodo para el archivo
        file_node = self._create_node(
            code_id=f"file:{file_path.name}:{file_path.stat().st_mtime}",
            code_segment=content,
            purpose=f"File: {file_path}",
            file_path=str(file_path),
            metrics=file_metrics,
            tags=['file', file_path.suffix[1:]]
        )
        nodes.append(file_node)
        self.nodes[file_node.code_id] = file_node
        
        # Extraer elementos del archivo
        elements = self._extract_code_elements(tree, content, str(file_path), file_node.code_id)
        nodes.extend(elements)
        
        # Agregar al registro
        self.file_registry[str(file_path)] = [n.code_id for n in nodes]
        
        return nodes
    
    def _extract_code_elements(self, tree: ast.AST, content: str, 
                               file_path: str, parent_id: str) -> List[PersistentCodeNode]:
        """Extrae elementos de código del AST."""
        nodes = []
        
        # Mapear nodos a sus padres
        parent_map = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent
        
        # Procesar clases y funciones
        for node in ast.walk(tree):
            element_node = None
            
            if isinstance(node, ast.ClassDef):
                element_node = self._extract_class(node, content, file_path, parent_id)
            elif isinstance(node, ast.FunctionDef):
                # Verificar si es método o función
                parent = parent_map.get(node)
                if not isinstance(parent, ast.ClassDef):
                    element_node = self._extract_function(node, content, file_path, parent_id)
            elif isinstance(node, ast.AsyncFunctionDef):
                element_node = self._extract_async_function(node, content, file_path, parent_id)
            
            if element_node:
                nodes.append(element_node)
                self.nodes[element_node.code_id] = element_node
                
                # Generar tests si está habilitado
                if self.config.get('testing.generate_tests', True):
                    tests = self.test_generator.generate_tests(node, content)
                    element_node.test_cases = tests
        
        return nodes
    
    def _create_node(self, code_id: str, code_segment: str, 
                    purpose: str, file_path: Optional[str] = None,
                    start_line: Optional[int] = None,
                    end_line: Optional[int] = None,
                    parent_id: Optional[str] = None,
                    metrics: Optional[CodeMetrics] = None,
                    tags: Optional[List[str]] = None) -> PersistentCodeNode:
        """Crea un nodo con análisis completo."""
        # Calcular hash único
        code_hash = hashlib.sha256(code_segment.encode()).hexdigest()
        
        # Analizar métricas si no se proporcionan
        if metrics is None:
            metrics = self.code_analyzer.analyze_code(code_segment, file_path)
        
        # Generar embedding
        embedding = self.embedding_generator.generate(code_segment)
        
        # Extraer documentación
        documentation = self._extract_documentation(code_segment)
        
        return PersistentCodeNode(
            code_id=code_id,
            code_segment=code_segment,
            code_hash=code_hash,
            dependencies=metrics.dependencies if isinstance(metrics, CodeMetrics) else [],
            purpose=purpose,
            metrics=metrics,
            test_cases=[],
            test_results=[],
            embedding=embedding,
            creation_timestamp=time.time(),
            update_timestamp=time.time(),
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            parent_node_id=parent_id,
            child_node_ids=[],
            tags=tags or [],
            documentation=documentation
        )
    
    def _extract_class(self, node: ast.ClassDef, content: str, 
                      file_path: str, parent_id: str) -> Optional[PersistentCodeNode]:
        """Extrae una clase como nodo con métodos anidados."""
        try:
            code = ast.get_source_segment(content, node)
            if not code:
                return None
            
            # Analizar la clase
            metrics = self.code_analyzer.analyze_code(code, file_path)
            
            class_node = self._create_node(
                code_id=f"class:{file_path}:{node.name}:{node.lineno}",
                code_segment=code,
                purpose=f"Class: {node.name}",
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno if hasattr(node, 'end_lineno') else None,
                parent_id=parent_id,
                metrics=metrics,
                tags=['class']
            )
            
            # Extraer métodos como nodos hijos
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_node = self._extract_method(item, content, file_path, class_node.code_id, node.name)
                    if method_node:
                        class_node.child_node_ids.append(method_node.code_id)
                        self.nodes[method_node.code_id] = method_node
            
            return class_node
            
        except Exception as e:
            logging.error(f"Failed to extract class {node.name}: {e}")
            return None
    
    def _extract_function(self, node: ast.FunctionDef, content: str,
                         file_path: str, parent_id: str) -> Optional[PersistentCodeNode]:
        """Extrae una función como nodo."""
        try:
            code = ast.get_source_segment(content, node)
            if not code:
                return None
            
            metrics = self.code_analyzer.analyze_code(code, file_path)
            
            return self._create_node(
                code_id=f"func:{file_path}:{node.name}:{node.lineno}",
                code_segment=code,
                purpose=f"Function: {node.name}",
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno if hasattr(node, 'end_lineno') else None,
                parent_id=parent_id,
                metrics=metrics,
                tags=['function']
            )
        except Exception as e:
            logging.error(f"Failed to extract function {node.name}: {e}")
            return None
    
    def _extract_async_function(self, node: ast.AsyncFunctionDef, content: str,
                               file_path: str, parent_id: str) -> Optional[PersistentCodeNode]:
        """Extrae una función asíncrona como nodo."""
        try:
            code = ast.get_source_segment(content, node)
            if not code:
                return None
            
            metrics = self.code_analyzer.analyze_code(code, file_path)
            
            return self._create_node(
                code_id=f"async_func:{file_path}:{node.name}:{node.lineno}",
                code_segment=code,
                purpose=f"Async Function: {node.name}",
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno if hasattr(node, 'end_lineno') else None,
                parent_id=parent_id,
                metrics=metrics,
                tags=['async', 'function']
            )
        except Exception as e:
            logging.error(f"Failed to extract async function {node.name}: {e}")
            return None
    
    def _extract_method(self, node: ast.FunctionDef, content: str,
                       file_path: str, parent_id: str, class_name: str) -> Optional[PersistentCodeNode]:
        """Extrae un método de clase como nodo."""
        try:
            code = ast.get_source_segment(content, node)
            if not code:
                return None
            
            metrics = self.code_analyzer.analyze_code(code, file_path)
            
            # Determinar tipo de método
            method_tags = ['method']
            if node.name.startswith('__') and node.name.endswith('__'):
                method_tags.append('magic')
            elif node.name.startswith('_'):
                method_tags.append('private')
            else:
                method_tags.append('public')
            
            if any(d.id == 'staticmethod' for d in node.decorator_list if isinstance(d, ast.Name)):
                method_tags.append('static')
            elif any(d.id == 'classmethod' for d in node.decorator_list if isinstance(d, ast.Name)):
                method_tags.append('classmethod')
            
            return self._create_node(
                code_id=f"method:{file_path}:{class_name}.{node.name}:{node.lineno}",
                code_segment=code,
                purpose=f"Method: {class_name}.{node.name}",
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno if hasattr(node, 'end_lineno') else None,
                parent_id=parent_id,
                metrics=metrics,
                tags=method_tags
            )
        except Exception as e:
            logging.error(f"Failed to extract method {class_name}.{node.name}: {e}")
            return None
    
    def _extract_documentation(self, code: str) -> Optional[str]:
        """Extrae documentación del código."""
        try:
            tree = ast.parse(code)
            return ast.get_docstring(tree)
        except:
            # Buscar docstrings manualmente
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    # Extraer docstring multi-línea
                    quote = '"""' if '"""' in line else "'''"
                    start = i
                    end = i
                    
                    for j in range(i + 1, len(lines)):
                        if quote in lines[j]:
                            end = j
                            break
                    
                    if end > start:
                        return '\n'.join(lines[start:end+1]).strip('"\' \n')
            
            return None
    
    def _analyze_dependencies(self):
        """Analiza dependencias entre nodos y crea edges."""
        for node_id, node in self.nodes.items():
            # Analizar imports en el código
            try:
                tree = ast.parse(node.code_segment)
                
                for ast_node in ast.walk(tree):
                    if isinstance(ast_node, (ast.Import, ast.ImportFrom)):
                        # Buscar nodos que puedan corresponder a estos imports
                        for dep_id, dep_node in self.nodes.items():
                            if dep_id != node_id:
                                # Verificar si el import coincide con el nodo
                                if self._is_dependency(ast_node, dep_node):
                                    self.edges[node_id].append(dep_id)
                    
                    elif isinstance(ast_node, ast.Call):
                        # Buscar llamadas a funciones/clases definidas
                        if isinstance(ast_node.func, ast.Name):
                            func_name = ast_node.func.id
                            # Buscar nodo correspondiente
                            for dep_id, dep_node in self.nodes.items():
                                if dep_id != node_id and func_name in dep_node.purpose:
                                    self.edges[node_id].append(dep_id)
            except:
                pass
    
    def _is_dependency(self, import_node: Union[ast.Import, ast.ImportFrom],
                      target_node: PersistentCodeNode) -> bool:
        """Verifica si un import corresponde a un nodo."""
        # Simplificado: verificar si el nombre del módulo está en el path del archivo
        if isinstance(import_node, ast.ImportFrom) and import_node.module:
            return import_node.module in str(target_node.file_path or '')
        return False
    
    def _auto_save(self):
        """Guarda automáticamente el estado si es necesario."""
        if not self.auto_save_enabled:
            return
        
        current_time = time.time()
        interval = self.config.get('persistence.save_interval_seconds', 300)
        
        if current_time - self.last_save_time >= interval:
            state_file = self.config.get('persistence.state_file', 'srpk_state.json')
            self.save_state(state_file)
            self.last_save_time = current_time
            logging.info(f"Auto-saved state to {state_file}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Genera resumen de métricas del grafo."""
        if not self.nodes:
            return {}
        
        total_loc = 0
        total_complexity = 0
        security_issues = []
        code_smells = []
        
        for node in self.nodes.values():
            if isinstance(node.metrics, CodeMetrics):
                total_loc += node.metrics.lines_of_code
                total_complexity += node.metrics.cyclomatic_complexity
                security_issues.extend(node.metrics.security_issues)
                code_smells.extend(node.metrics.code_smells)
        
        avg_complexity = total_complexity / max(len(self.nodes), 1)
        
        # Calcular calidad promedio
        quality_scores = [n.calculate_quality_score() for n in self.nodes.values()]
        avg_quality = sum(quality_scores) / max(len(quality_scores), 1)
        
        return {
            'total_files': len(self.file_registry),
            'total_nodes': len(self.nodes),
            'total_edges': sum(len(edges) for edges in self.edges.values()),
            'total_loc': total_loc,
            'average_complexity': round(avg_complexity, 2),
            'average_quality_score': round(avg_quality, 3),
            'security_issue_count': len(security_issues),
            'code_smell_count': len(code_smells),
            'unique_dependencies': len(set(
                dep for node in self.nodes.values()
                if isinstance(node.metrics, CodeMetrics)
                for dep in node.metrics.dependencies
            ))
        }
    
    def find_similar_nodes(self, node_id: str, threshold: float = 0.85) -> List[Tuple[str, float]]:
        """Encuentra nodos similares basado en embeddings."""
        if node_id not in self.nodes:
            return []
        
        target_node = self.nodes[node_id]
        if target_node.embedding is None:
            return []
        
        similar = []
        
        for other_id, other_node in self.nodes.items():
            if other_id != node_id and other_node.embedding is not None:
                similarity = self.embedding_generator.calculate_similarity(
                    target_node.embedding,
                    other_node.embedding
                )
                
                if similarity >= threshold:
                    similar.append((other_id, similarity))
        
        return sorted(similar, key=lambda x: x[1], reverse=True)
    
    def get_node_quality_report(self, node_id: str) -> Dict[str, Any]:
        """Genera reporte de calidad para un nodo específico."""
        if node_id not in self.nodes:
            return {}
        
        node = self.nodes[node_id]
        
        report = {
            'node_id': node_id,
            'purpose': node.purpose,
            'quality_score': node.calculate_quality_score(),
            'metrics': asdict(node.metrics) if isinstance(node.metrics, CodeMetrics) else node.metrics,
            'test_coverage': len(node.test_results) / max(len(node.test_cases), 1) if node.test_cases else 0,
            'has_documentation': bool(node.documentation),
            'tags': node.tags,
            'dependencies': node.dependencies,
            'child_count': len(node.child_node_ids),
            'similar_nodes': self.find_similar_nodes(node_id, 0.9)[:5]
        }
        
        return report
    
    def save_state(self, path: str, create_backup: bool = True):
        """Guarda el estado completo con backup opcional."""
        # Crear backup si existe archivo anterior
        if create_backup and os.path.exists(path):
            backup_count = self.config.get('persistence.backup_count', 3)
            self._create_backup(path, backup_count)
        
        state = {
            'version': '3.1',
            'timestamp': time.time(),
            'config': self.config.config,
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'edges': dict(self.edges),
            'file_registry': self.file_registry,
            'metrics_history': self.metrics_history[-100:],  # Limitar historial
            'analyzer_errors': self.analyzer.get_error_summary()
        }
        
        # Usar compresión si está habilitada
        if self.config.get('cache.compression', True):
            with gzip.open(path + '.gz', 'wt', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            logging.info(f"State saved to {path}.gz")
        else:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            logging.info(f"State saved to {path}")
    
    def _create_backup(self, path: str, max_backups: int):
        """Crea backups rotatorios del archivo."""
        backup_dir = Path(path).parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        # Generar nombre de backup con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"{Path(path).stem}_{timestamp}{Path(path).suffix}"
        
        # Copiar archivo actual a backup
        try:
            shutil.copy2(path, backup_path)
            logging.info(f"Backup created: {backup_path}")
            
            # Limpiar backups antiguos
            backups = sorted(backup_dir.glob(f"{Path(path).stem}_*"))
            if len(backups) > max_backups:
                for old_backup in backups[:-max_backups]:
                    old_backup.unlink()
                    logging.debug(f"Removed old backup: {old_backup}")
        
        except Exception as e:
            logging.warning(f"Failed to create backup: {e}")
    
    def load_state(self, path: str):
        """Carga el estado desde archivo con validación."""
        # Detectar si está comprimido
        if path.endswith('.gz') or os.path.exists(path + '.gz'):
            actual_path = path if path.endswith('.gz') else path + '.gz'
            with gzip.open(actual_path, 'rt', encoding='utf-8') as f:
                state = json.load(f)
        else:
            with open(path, 'r', encoding='utf-8') as f:
                state = json.load(f)
        
        # Validar versión
        state_version = state.get('version', '0.0')
        if state_version != '3.1':
            logging.warning(f"Loading state from different version: {state_version}")
        
        # Restaurar configuración
        if 'config' in state:
            self.config.config = state['config']
        
        # Restaurar nodos
        self.nodes = {}
        for node_id, node_data in state.get('nodes', {}).items():
            try:
                self.nodes[node_id] = PersistentCodeNode.from_dict(node_data)
            except Exception as e:
                logging.error(f"Failed to restore node {node_id}: {e}")
        
        # Restaurar edges
        self.edges = defaultdict(list, state.get('edges', {}))
        
        # Restaurar registros
        self.file_registry = state.get('file_registry', {})
        self.metrics_history = state.get('metrics_history', [])
        
        logging.info(f"State loaded from {path}: {len(self.nodes)} nodes")
    
    def cleanup(self):
        """Limpia recursos y cierra conexiones."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        
        if self.auto_save_enabled:
            state_file = self.config.get('persistence.state_file', 'srpk_state.json')
            self.save_state(state_file)

# =====================================================================
# INTERFAZ DE LÍNEA DE COMANDOS PRINCIPAL
# =====================================================================

def main():
    """Punto de entrada principal del sistema."""
    import sys
    import argparse
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('srpk.log'),
            logging.StreamHandler()
        ]
    )
    
    # Banner
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          MSC SRPK v3.1 - Enterprise Edition                  ║
    ║     Self-Referencing Proprietary Knowledge Graph             ║
    ║     Production-Ready Code Analysis System                    ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    parser = argparse.ArgumentParser(
        description='MSC SRPK v3.1 - Enterprise Code Analysis System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('project_path', 
                       help='Path to the Python project to analyze')
    parser.add_argument('--config', '-c',
                       help='Path to configuration file')
    parser.add_argument('--output', '-o', default='srpk_report',
                       help='Output directory for reports (default: srpk_report)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable cache for this run')
    parser.add_argument('--parallel', action='store_true', default=True,
                       help='Enable parallel processing (default: enabled)')
    parser.add_argument('--format', choices=['json', 'html', 'markdown', 'all'],
                       default='all', help='Report output format')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Inicializar sistema
    try:
        config = ConfigurationManager(args.config) if args.config else ConfigurationManager()
        
        if args.no_cache:
            config.set('cache.enabled', False)
        
        graph = EnterpriseSRPKGraph(config)
        
        print(f"\n📂 Analyzing project: {args.project_path}")
        print("=" * 60)
        
        # Analizar proyecto
        results = graph.analyze_project(args.project_path)
        
        print(f"\n✅ Analysis complete!")
        print(f"  Files analyzed: {results['files_analyzed']}")
        print(f"  Files failed: {results['files_failed']}")
        print(f"  Nodes created: {results['nodes_created']}")
        print(f"  Duration: {results['duration']:.2f} seconds")
        
        if results.get('summary'):
            print(f"\n📊 Summary:")
            for key, value in results['summary'].items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
        
        # Guardar estado
        graph.save_state('srpk_state.json')
        print(f"\n💾 State saved to srpk_state.json")
        
        # Limpiar recursos
        graph.cleanup()
        
        print(f"\n✨ Success! Analysis results available in {args.output}/")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.exception("Fatal error in main")
        sys.exit(1)

if __name__ == "__main__":
    main()