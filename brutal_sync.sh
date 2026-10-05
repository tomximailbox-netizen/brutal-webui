#!/bin/bash

# ============================================================
# brutalctl DNS IP 自动同步 (支持 IPv4 /32 与 IPv6 /128)
#
# 用法：
#   ./brutal_sync.sh /path/to/domains.txt [exclude-ips-file]
#
# domains.txt 格式：
#
#   google.com
#   cloudflare.com
#   github.com
#
#   # 支持注释
#
# 功能：
#   1. 从文件读取域名，每行一个
#   2. 解析所有域名的 IPv4 和 IPv6
#   3. DNS 新 IP -> brutalctl add IP/32 100 (IPv4) 或 IP/128 100 (IPv6)
#   4. 已存在 IP -> 跳过
#   5. brutalctl 旧 IP -> brutalctl del IP/32 (IPv4) 或 IP/128 (IPv6)
#   6. 自动去重与手动白名单保护
#   7. 不删除非 /32 与非 /128 的网段规则
#   8. 所有域名解析失败时，不执行任何删除操作
# ============================================================

set -u

BRUTALCTL="brutalctl"
RATE_MBPS="100"

get_cidr_mask() {
    local ip="$1"
    case "$ip" in
        *:*) echo "128" ;;
        *)   echo "32" ;;
    esac
}

get_target_rule() {
    local ip="$1"
    local mask
    mask=$(get_cidr_mask "$ip")
    echo "${ip}/${mask}"
}

# ============================================================
# 检查参数
# ============================================================

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "用法：$0 <domain-file> [exclude-ips-file]"
    echo
    echo "例如："
    echo "  $0 /root/domains.txt"
    echo "  $0 /root/domains.txt /root/manual_excludes.txt"
    exit 1
fi

DOMAIN_FILE="$1"
EXCLUDE_FILE="${2:-}"

# ============================================================
# 检查域名文件
# ============================================================

if [ ! -f "$DOMAIN_FILE" ]; then
    echo "错误：文件不存在：$DOMAIN_FILE"
    exit 1
fi

if [ ! -r "$DOMAIN_FILE" ]; then
    echo "错误：文件无法读取：$DOMAIN_FILE"
    exit 1
fi

# ============================================================
# 检查 brutalctl
# ============================================================

if ! command -v "$BRUTALCTL" >/dev/null 2>&1; then
    echo "错误：找不到 brutalctl"
    exit 1
fi

# ============================================================
# 检查 root
# ============================================================

if [ "$(id -u)" -ne 0 ]; then
    echo "错误：请使用 root 或 sudo 执行。"
    exit 1
fi

# ============================================================
# 临时文件
# ============================================================

DNS_IPS=$(mktemp)
CURRENT_IPS=$(mktemp)

cleanup() {
    rm -f "$DNS_IPS" "$CURRENT_IPS"
}

trap cleanup EXIT

# ============================================================
# 1. 读取域名文件并解析
# ============================================================

echo
echo "========================================"
echo "读取域名文件"
echo "========================================"

echo "文件：$DOMAIN_FILE"

DOMAIN_COUNT=0
RESOLVED_DOMAIN_COUNT=0

while IFS= read -r domain || [ -n "$domain" ]; do

    # 去掉 UTF-8 BOM
    domain="${domain#$'\xef\xbb\xbf'}"

    # 去掉首尾空格
    domain=$(echo "$domain" | xargs)

    # 跳过空行
    [ -z "$domain" ] && continue

    # 跳过注释
    case "$domain" in
        \#*)
            continue
            ;;
    esac

    DOMAIN_COUNT=$((DOMAIN_COUNT + 1))

    # 提取域名与自定义速率（例如 google.com 200，若未提供则默认 100Mbps）
    domain_name=$(echo "$domain" | awk '{print $1}')
    domain_rate=$(echo "$domain" | awk '{print $2}')
    if [ -z "$domain_rate" ] || ! [[ "$domain_rate" =~ ^[0-9]+$ ]]; then
        domain_rate="$RATE_MBPS"
    fi

    echo
    echo "[DNS] $domain_name (限速: ${domain_rate} Mbps)"

    # 获取 IPv4 与 IPv6
    ips_v4=$(getent ahostsv4 "$domain_name" 2>/dev/null | awk '{print $1}' || true)
    ips_v6=$(getent ahostsv6 "$domain_name" 2>/dev/null | awk '{print $1}' || true)
    ips=$(printf "%s\n%s\n" "$ips_v4" "$ips_v6" | sed '/^$/d' | sort -u)

    # 兜底：如果 ahostsv4/v6 无输出，尝试通用 ahosts
    if [ -z "$ips" ]; then
        ips=$(getent ahosts "$domain_name" 2>/dev/null | awk '{print $1}' | sort -u || true)
    fi

    # 严格过滤 IPv4 映射/兼容格式的 ::ffff: 伪 IPv6 地址
    ips=$(printf "%s\n" "$ips" | grep -vEi '::ffff:' | sed '/^$/d' | sort -u || true)

    if [ -z "$ips" ]; then

        echo "  没有解析到有效 IPv4 或原生 IPv6"

        continue
    fi

    RESOLVED_DOMAIN_COUNT=$((RESOLVED_DOMAIN_COUNT + 1))

    while IFS= read -r ip; do

        [ -z "$ip" ] && continue

        # 双重防御：坚决跳过 ::ffff: 兼容地址
        case "$ip" in
            *::ffff:*|*::FFFF:*)
                echo "  [跳过] 排除 IPv4 兼容映射地址: $ip"
                continue
                ;;
        esac

        mask=$(get_cidr_mask "$ip")
        echo "  -> $ip (/${mask}) [${domain_rate} Mbps]"

        echo "$ip $domain_rate" >> "$DNS_IPS"

    done <<< "$ips"

done < "$DOMAIN_FILE"


# ============================================================
# DNS IP 去重 (按第一列 IP 唯一保留)
# ============================================================

awk '!seen[$1]++' "$DNS_IPS" > "${DNS_IPS}.tmp" && mv "${DNS_IPS}.tmp" "$DNS_IPS"

DNS_COUNT=$(wc -l < "$DNS_IPS")


echo
echo "========================================"
echo "DNS 解析结果"
echo "========================================"

echo "域名数量       : $DOMAIN_COUNT"
echo "解析成功       : $RESOLVED_DOMAIN_COUNT"
echo "唯一 IP (v4/v6): $DNS_COUNT"


# ============================================================
# 安全检查
#
# 如果所有域名都解析失败：
#   不执行 ADD / DEL，防止 DNS 临时故障导致原有规则被清空。
# ============================================================

if [ "$DOMAIN_COUNT" -eq 0 ]; then

    echo
    echo "错误：域名清单中没有有效域名。"
    exit 1

fi

if [ "$DOMAIN_COUNT" -gt 0 ] && [ "$RESOLVED_DOMAIN_COUNT" -eq 0 ]; then

    echo
    echo "错误：所有域名都解析失败。"
    echo "为了安全，本次不执行任何 ADD/DEL 操作。"

    exit 1

fi


# ============================================================
# 2. 获取 brutalctl 当前 /32 IP
# ============================================================

echo
echo "========================================"
echo "当前 brutalctl"
echo "========================================"

"$BRUTALCTL" list


# brutalctl list 格式：
#
# DESTINATION                     RATE(Mbps)  GAIN  LOCK  ROUTE   ID  MEMBERS   SENT(MB)
# 123.145.97.17/32                    100.00    20   yes    yes    1       39      616.5
#
# 第一列就是 DESTINATION

"$BRUTALCTL" list 2>/dev/null |
    awk '
        NR > 1 {
            if ($1 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\/32$/) {
                ip = $1
                sub(/\/32$/, "", ip)
                print ip
            } else if ($1 ~ /^[0-9a-fA-F:.]+\/128$/) {
                ip = $1
                sub(/\/128$/, "", ip)
                print ip
            }
        }
    ' |
    sort -u > "$CURRENT_IPS"


CURRENT_COUNT=$(wc -l < "$CURRENT_IPS")

echo
echo "当前 /32(v4) 与 /128(v6) IP : $CURRENT_COUNT"


# ============================================================
# 3. 添加新 IP
# ============================================================

echo
echo "========================================"
echo "添加新 IP"
echo "========================================"

ADD_COUNT=0
SKIP_COUNT=0

while IFS= read -r line; do

    [ -z "$line" ] && continue

    ip=$(echo "$line" | awk '{print $1}')
    rate=$(echo "$line" | awk '{print $2}')
    [ -z "$rate" ] && rate="$RATE_MBPS"

    rule=$(get_target_rule "$ip")

    if grep -Fxq "$ip" "$CURRENT_IPS"; then

        echo "[SKIP] $rule 已存在 (${rate} Mbps)"

        SKIP_COUNT=$((SKIP_COUNT + 1))

    else

        echo "[ADD ] $rule ${rate} Mbps"

        if "$BRUTALCTL" add "$rule" "$rate"; then

            echo "       -> 成功"

            ADD_COUNT=$((ADD_COUNT + 1))

        else

            echo "       -> 失败"

        fi

    fi

done < "$DNS_IPS"


# ============================================================
# 4. 删除旧 IP
#
# brutalctl 中存在，但当前 DNS 中已经不存在
# ============================================================

echo
echo "========================================"
echo "删除失效 IP"
echo "========================================"

DEL_COUNT=0

while IFS= read -r ip; do

    [ -z "$ip" ] && continue

    rule=$(get_target_rule "$ip")

    if awk '{print $1}' "$DNS_IPS" | grep -Fxq "$ip"; then

        echo "[KEEP] $rule (DNS 解析有效)"

    elif [ -n "$EXCLUDE_FILE" ] && [ -f "$EXCLUDE_FILE" ] && grep -Fxq "$ip" "$EXCLUDE_FILE"; then

        echo "[KEEP] $rule (手动添加规则，保留)"

    else

        echo "[DEL ] $rule"

        if "$BRUTALCTL" del "$rule"; then

            echo "       -> 成功"

            DEL_COUNT=$((DEL_COUNT + 1))

        else

            echo "       -> 失败"

        fi

    fi

done < "$CURRENT_IPS"


# ============================================================
# 5. 最终结果
# ============================================================

echo
echo "========================================"
echo "同步完成"
echo "========================================"

echo "域名数量       : $DOMAIN_COUNT"
echo "DNS IPv4       : $DNS_COUNT"
echo "已存在         : $SKIP_COUNT"
echo "新增           : $ADD_COUNT"
echo "删除           : $DEL_COUNT"

echo
echo "最终 brutalctl："

"$BRUTALCTL" list
