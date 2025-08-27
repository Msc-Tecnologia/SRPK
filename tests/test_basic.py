import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_import():
    """Test que el módulo se puede importar"""
    try:
        import srpk_v3_1
        assert True
    except ImportError:
        assert False, "No se pudo importar srpk_v3_1"

def test_configuration():
    """Test básico de configuración"""
    from srpk_v3_1 import ConfigurationManager
    config = ConfigurationManager()
    assert config is not None
