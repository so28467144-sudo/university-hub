"""Split public data and durable state, with a public-file commit point."""
import hashlib
import json
import uuid
from pathlib import Path

STATE_PATH = '_internal/news-preservation.json'
INTERNAL_KEYS = {'raw_news', 'raw_news_schema_version', 'region_change_reviews', 'search_cursor', 'pending_update'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def public_rows(rows):
    return [{k:v for k,v in row.items() if k != 'pending_update'} for row in rows]


def load_state(root, public):
    marker = public.get('preservation')
    path = Path(root)/STATE_PATH
    if not marker:
        if path.exists(): raise ValueError('Orphan preservation state: explicit recovery required')
        return public  # Explicit legacy migration; never used for a split dataset.
    if not isinstance(marker,dict): raise ValueError('Invalid preservation marker')
    if marker.get('path') != STATE_PATH: raise ValueError('Unexpected preservation path')
    blob = path.read_bytes()
    if digest(blob) != marker.get('sha256'): raise ValueError('Preservation SHA256 mismatch')
    state = json.loads(blob)
    encode(state)
    if not isinstance(state,dict) or state.get('schema_version') != 1: raise ValueError('Unsupported preservation schema')
    if state.get('generation') != marker.get('generation'): raise ValueError('Preservation generation mismatch')
    payload = {k:v for k,v in public.items() if k != 'preservation'}
    if state.get('public_sha256') != digest(encode(payload)): raise ValueError('Public generation content mismatch')
    if not isinstance(state.get('raw_news'), list): raise ValueError('Missing durable raw records')
    if not {row['id'] for row in public['news']} <= {row['id'] for row in state['raw_news']}:
        raise ValueError('Public IDs missing from durable raw records')
    restored=dict(public, raw_news=state['raw_news'], region_change_reviews=state.get('region_change_reviews', []),
                  search_cursor=state.get('search_cursor', 0))
    if 'pending_update' in state: restored['pending_update']=state['pending_update']
    return restored


def prepare_pair(output):
    generation = uuid.uuid4().hex
    public = {k:v for k,v in output.items() if k not in INTERNAL_KEYS and k != 'preservation'}
    public['news'] = public_rows(output['news'])
    # Preserve legacy extension fields, but never expose internal article updates.
    state = dict(schema_version=1, generation=generation, public_sha256=digest(encode(public)),
                 raw_news=output['raw_news'], region_change_reviews=output.get('region_change_reviews', []),
                 search_cursor=output.get('search_cursor', 0))
    if 'pending_update' in output: state['pending_update']=output['pending_update']
    state_blob = encode(state)
    public['preservation'] = dict(path=STATE_PATH, generation=generation, sha256=digest(state_blob))
    return encode(public), state_blob


def write_pair(root, public_blob, state_blob):
    root=Path(root); public_path=root/'news.json'; state_path=root/STATE_PATH
    state_path.parent.mkdir(parents=True,exist_ok=True)
    old_public=public_path.read_bytes() if public_path.exists() else None
    old_state=state_path.read_bytes() if state_path.exists() else None
    public_temp=root/'news.publish.tmp'; state_temp=state_path.with_suffix('.tmp')
    # Prepare both files before replacing either. Keep the previous durable state
    # for crash recovery; a mid-process interruption is rejected on the next run.
    public_temp.write_bytes(public_blob); state_temp.write_bytes(state_blob)
    if old_state is not None:
        state_path.with_suffix('.previous.json').write_bytes(old_state)
    try:
        state_temp.replace(state_path)
        public_temp.replace(public_path)  # Commit point: no throwing writes after it.
    except OSError:
        if old_state is None:
            if state_path.exists(): state_path.unlink()
        else:
            rollback=state_path.with_suffix('.rollback.tmp'); rollback.write_bytes(old_state); rollback.replace(state_path)
        if (public_path.read_bytes() if public_path.exists() else None) != old_public:
            raise RuntimeError('Unexpected public file change during failed publication')
        raise


def validate_pair(root):
    public=json.loads((Path(root)/'news.json').read_bytes())
    if not public.get('preservation'): raise ValueError('Split storage marker missing')
    return load_state(root,public)


if __name__=='__main__':
    validate_pair(Path(__file__).resolve().parent)
