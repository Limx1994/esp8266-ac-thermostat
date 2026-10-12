import hashlib
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
baseline = json.loads((OUT / 'recovery_baseline.json').read_text(encoding='utf-8-sig'))
report = json.loads((OUT / 'performance_result.json').read_text(encoding='utf-8-sig'))
catalog = json.loads((OUT / 'completeness_current_coverage.json').read_text(encoding='utf-8-sig'))
# Catalog supplies file identities only. Reading claims below concern this
# replacement specialist's actual source reading, plus the prior explicit
# current main.c/app.h/Kconfig/defaults full-reading record.
texts = {r['relative_path'] for r in catalog if r['status'] == 'current_full_text_read'}
licenses = {'LICENSE', 'Sof\\LICENSE', 'Sof\\tools\\esptool-v4.12.0\\LICENSE'}
cad = {'Ad\\PCB_Project.PrjPcb', 'Ad\\PCB_Project.PrjPcbStructure'}
texts -= licenses | cad
ledger = []
changes = []
for row in baseline:
    rel = row['Path']
    path = ROOT / rel
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    limit = ''
    if rel in texts:
        status = 'current_full_text_read'
        origin = '项目代码、脚本、MD、配置；sdk_component.cmake为SDK组件生成副本'
    elif rel.startswith('Sof\\build\\'):
        status = 'generated_registered'
        origin = '现有CMake/Ninja及SDK构建产物'
        limit = '按来源、接口和主控验证登记；未逐行语义审查生成物'
    elif '__pycache__' in rel:
        status = 'cache_registered'
        origin = '对应Python源文件的解释器缓存'
        limit = '不视为独立业务源码'
    elif rel in licenses:
        status = 'license_nonfunctional_registered'
        origin = '项目及附带工具许可'
        limit = '非执行文本；未进行法律审查'
    elif rel in cad:
        status = 'cad_project_registered'
        origin = 'Altium工程元数据'
        limit = '未以元数据证明电气、几何、实机性能'
    else:
        status = 'attachment_or_binary_registered'
        origin = '驱动archive、工具EXE、CAD/几何、datasheet、BOM、历史CSV或图片'
        limit = '未反编译或实机测量；历史数据不证明当前固件性能'
    match = digest.lower() == row['SHA256'].lower()
    if not match:
        changes.append(rel)
        if not rel.startswith('Sof\\build\\'):
            raise RuntimeError('Review input changed: ' + rel)
    ledger.append({'path': str(path), 'relative_path': rel, 'status': status,
                   'baseline_sha256': row['SHA256'], 'current_sha256': digest,
                   'baseline_match': match, 'origin': origin, 'limit': limit,
                   'lines_read': len(path.read_text(encoding='utf-8-sig').splitlines()) if rel in texts else 0})
assert len(ledger) == 912
assert len(texts) == 69
report['current_ledger'] = ledger
report['source_gaps'] = []
report['status'] = 'current_source_review_complete_with_binary_hardware_limits'
report['current_completion'] = {
    'full_text_count': 69, 'business_text_count': 68,
    'generated_sdk_text_count': 1, 'baseline_count': 912,
    'read_basis': '替补分块实际完整读当前全部tests/main依赖/HTTP/tools/build/flash/clean/MD/config；当前main完整读复用原明确当前hash记录，其余目标依赖重新完整读',
    'long_blocks': {'test_power.py': [[1,600],[601,1250],[1251,1950],[1951,2600],[2601,2991]],
                    'test_portal.py': [[1,680],[681,1360],[1361,1938]],
                    'httpd_parse.c': '1-430及431-EOF', 'README.md': '1-95、96-275、276-EOF'},
    'input_hash_drift': [], 'generated_hash_changes': changes,
    'scope_limits': 'LICENSE/CAD工程元数据仅登记；二进制/几何/测量附件与构建产物不能升级为语义审完；未连接硬件、未重跑共享测试',
    'candidates': [], 'confirmed_performance': []}
report['cross_review'] = [
    {'id':'DRIVER-EVAL', 'location':str(ROOT / 'Sof/tools/wifi_driver_eval.py') + ':112',
     'evidence':'当前工具、driver.cmake、noise_power.cmake和reproductions.json真实CMake属性复现已复核；7目标导入路径从shadow改回固定库。候选仅占位，未下载/完整评估/烧录。',
     'challenge':'noise_power会再次指定core/pp aliases；修评估路径必须让候选archive与aliases同源，保留生产固定858校验。--latest不套用不同版本错链结论。',
     'conclusion':'认可功能问题；没有候选实际吞吐/电流量化对比，不列性能缺陷。'},
    {'id':'NINJA-HEADER', 'location':str(ROOT / 'Sof/tests/build.ninja') + ':2',
     'evidence':'当前rule无depfile；reproductions.json记录初次0、改header后Ninja0无工作、旧exe0、freshGCC1。',
     'challenge':'run_coverage.rules直接GCC重新编译，不受同一增量入口影响；建议depfile或明确header依赖，不强制每次clean。',
     'conclusion':'认可Bug；修复应仅重编必要对象。cases改动预期1编译1链接、rules.h改动2编译1链接、无变更0；未实施验证修复。'},
    {'id':'CONTROL-MOCK', 'location':str(ROOT / 'Sof/tests/test_power.py') + ':28',
     'evidence':'当前SDK/CONTROL全文缺wifi_config_t、ESP_IF_WIFI_AP及get/set mock；主控coverage首CONTROL失败；独立control_mock_repro.json syntax-only exit1。',
     'challenge':'main新调用只在开启热点后执行一次；主机mock编译失败不能推导生产固件性能回归。不要删除实际生产调用或功耗测试回避失败。',
     'conclusion':'认可主机mock功能完成度回归；仅建议补mock并复跑已有矩阵，不宣称生产固件崩溃或功耗退化。'},
    {'id':'DEAD-CODE-CROSS', 'conclusion':'wrap由链接选项引用，RAM诊断有report消费者；固定archive/ABI输入不能按未被直接源码引用认定死代码。'}]
report['validation'] = {'source_modified':False, 'new_tests_executed':False,
                        'current_shared':'主控重建固件通过；coverage当前10检查组通过1失败、22Python通过；功耗首CONTROL编译阻断，6模块未形成有效覆盖。性能专员只读复核，不冒充实机测量。'}
(OUT / 'performance_result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'ledger':len(ledger), 'full_text':len(texts), 'status_counts':dict(Counter(r['status'] for r in ledger)), 'source_gaps':[], 'generated_changes':len(changes), 'confirmed_performance':0}, ensure_ascii=False))
