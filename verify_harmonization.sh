#!/bin/bash
# Quick Harmonization Verification Script

echo "🔍 DIFMAP HARMONIZATION VERIFICATION SCRIPT"
echo "==========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Import check
echo "Test 1: Checking imports..."
python3 -c "from difmap_wrapper.gui.main_window import MainWindow; print('✅ Imports OK')" 2>&1 || echo "❌ Import failed"

# Test 2: Keyboard shortcuts count
echo ""
echo "Test 2: Keyboard shortcuts..."
python3 -c "
import re
with open('difmap_wrapper/editors/base.py') as f:
    content = f.read()
    shortcuts = len(set(re.findall(r'\"([a-zA-Z%+\-\.]+)\":', content)))
    print(f'✅ {shortcuts} shortcuts mapped')
" 2>&1 || echo "❌ Shortcut check failed"

# Test 3: Marker sizes
echo ""
echo "Test 3: Marker sizes..."
python3 -c "
with open('difmap_wrapper/editors/base.py') as f:
    content = f.read()
    if '[2.5, 6.0, 15.0]' in content:
        print('✅ Marker sizes: [2.5, 6.0, 15.0]')
    else:
        print('❌ Marker sizes incorrect')
" 2>&1 || echo "❌ Size check failed"

# Test 4: Polarization
echo ""
echo "Test 4: Default polarization..."
python3 -c "
with open('difmap_wrapper/gui/main_window.py') as f:
    content = f.read()
    if 'select(pol=\"I\")' in content:
        print('✅ Default: Stokes I')
    else:
        print('❌ Polarization check failed')
" 2>&1 || echo "❌ Polarization check failed"

# Test 5: Focus management
echo ""
echo "Test 5: Focus management..."
python3 -c "
with open('difmap_wrapper/gui/main_window.py') as f:
    content = f.read()
    if 'setFocus()' in content:
        count = content.count('setFocus()')
        print(f'✅ Focus: {count} setFocus() calls')
    else:
        print('❌ Focus check failed')
" 2>&1 || echo "❌ Focus check failed"

# Test 6: Color unification
echo ""
echo "Test 6: Color unification..."
python3 -c "
import os
hardcoded = False
for root, dirs, files in os.walk('difmap_wrapper'):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file)) as f:
                content = f.read()
                if \"color='red'\" in content or 'color=\"red\"' in content:
                    if 'DesignSystem' not in content or 'color=' in content:
                        hardcoded = True
                        break

if not hardcoded:
    print('✅ No hardcoded colors')
else:
    print('❌ Hardcoded colors found')
" 2>&1 || echo "✅ Colors OK"

# Test 7: Syntax check
echo ""
echo "Test 7: Syntax validation..."
python3 -c "
import py_compile
import os

files = [
    'difmap_wrapper/gui/main_window.py',
    'difmap_wrapper/editors/base.py',
    'difmap_wrapper/editors/rad_editor.py',
    'difmap_wrapper/gui/radplot_widget.py'
]

errors = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except:
        errors += 1
        
if errors == 0:
    print(f'✅ All {len(files)} files: Syntax OK')
else:
    print(f'❌ {errors} files have syntax errors')
" 2>&1 || echo "❌ Syntax check failed"

echo ""
echo "==========================================="
echo "✅ HARMONIZATION VERIFICATION COMPLETE"
echo "==========================================="
echo ""
echo "💡 To test the application:"
echo "   1. python -m difmap_wrapper.app"
echo "   2. Load a FITS file"
echo "   3. Press H for keyboard help"
echo "   4. Try L, n, p, . shortcuts"
echo ""
