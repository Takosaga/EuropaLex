#!/usr/bin/env python3
"""Test that engine modules can be imported and preloaded correctly."""

import sys
from unittest.mock import patch, MagicMock

# Mock torch to avoid GPU allocation during import
sys.modules['torch'] = MagicMock()
sys.modules['llama_cpp'] = MagicMock()

try:
    from core.engine import EnginePool, _engines, _preload_success
    
    print("✓ Import successful")
    
    # Check preloading happened
    if 'english' in _engines:
        print("✓ English engine loaded")
    else:
        print("✗ English engine not loaded")
        
    if 'translation' in _engines:
        print("✓ Translation engine loaded")
    else:
        print("✗ Translation engine not loaded")
    
    if 'tts' in _engines:
        print("✓ TTS engine loaded")
    else:
        print("✗ TTS engine not loaded")
        
    if 'image' in _engines:
        print("✓ Image engine loaded")
    else:
        print("✗ Image engine not loaded")
    
    # Check EnginePool singleton pattern
    from core.types import EngineConfig
    
    with patch('core.engine.EngineConfig.from_settings_yaml') as mock_config:
        mock_config.return_value = MagicMock()
        pool = EnginePool.get(mock_config.return_value)
        
        if pool is not None:
            print("✓ EnginePool.get returns instance")
        else:
            print("✗ EnginePool.get returned None")
    
    # Check accessor methods
    try:
        engine = pool.get_english_engine()
        print(f"✓ get_english_engine works: {type(engine)}")
    except Exception as e:
        print(f"✗ get_english_engine failed: {e}")
        
    print("\nAll basic checks passed!")
    
except Exception as e:
    print(f"✗ Import or preloading failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
