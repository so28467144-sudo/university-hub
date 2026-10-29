"""전체 대학명에서 일관되게 약칭 후보를 생성합니다."""
import re

SUFFIXES = [
    ('과학기술대학교','과기대'), ('외국어대학교','외대'),
    ('여자대학교','여대'), ('여자대학','여대'),
    ('공과대학교','공대'), ('체육대학교','체대'),
    ('예술대학교','예대'), ('예술대학','예대'),
    ('전문대학교','전문대'), ('전문대학','전문대'),
    ('대학교','대'), ('대학','대'),
]


def generate_aliases(name,extra=()):
    bases={name,name.removeprefix('국립')}
    if '국립' in name:bases.add(name.replace('국립',''))
    aliases=set(bases)|set(extra)
    for base in bases:
        for ending,short in SUFFIXES:
            if base.endswith(ending):aliases.add(base[:-len(ending)]+short)
        if re.fullmatch(r'[가-힣]{2}교육대학교',base):aliases.add(base.replace('교육대학교','교대'))
        # 공통 약칭은 후보로만 등록하며 단일 대학으로 강제 연결하지 않습니다.
        for ending,short in [('교육대학교','교대'),('외국어대학교','외대'),('과학기술대학교','과기대'),('예술대학교','예대')]:
            if base.endswith(ending):aliases.add(short)
    return {alias for alias in aliases if alias}
