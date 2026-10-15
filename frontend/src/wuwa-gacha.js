export function pityText(pity) {
  if (pity?.status === 'exact') return `当前垫抽 ${pity.count}`
  if (pity?.status === 'lower_bound') return `当前垫抽至少 ${pity.count}`
  return '当前垫抽未知'
}
export function aggregateKind(item) {
  return item?.kind === 'current_count' ? '来源自报当前垫抽' : '来源自报五星周期抽数'
}
const REASONS = {
  pool_reset_sharing_rule: '缺少卡池重置与共享规则',
  latest_records_confirmation: '最新范围尚未确认',
  continuous_records_confirmation: '逐抽连续性尚未确认',
  resolve_source_warnings: '来源存在缺口或未解决警告',
  known_records_missing_from_segment: '本段未包含部分已知记录',
  same_timestamp_order_unknown: '同一时间五星与其他记录的先后未知',
  source_time_basis_mixed: '来源时区基准混合',
  pull_semantics_unknown: '部分记录的抽数或稀有度未知',
  rule_record_conflict: '记录与用户规则冲突',
  UNKNOWN_POOL: '未知卡池，保留来源标识',
  UNKNOWN_RESOURCE: '物品 ID 未映射，保留来源名称',
  CONTINUITY_UNVERIFIED: '逐抽连续性未证实',
  SERVER_BOUND_BY_CURRENT_ACCOUNT: '来源缺少区服，按当前账号区服绑定',
}
export function gachaReason(reason) { return REASONS[reason] || reason }
export function gachaSource(source) {
  return { official_query:'官方记录查询', json_import:'JSON / 本项目归档', mcgf:'mcgf 五星汇总',
    xhh:'xhh 五星汇总', legacy:'旧账本（来源未知）' }[source] || '来源未记录'
}
