import streamlit as st
import pandas as pd
import numpy as np

# 设置页面配置
st.set_page_config(page_title="七分钟投顾组合调仓明细", page_icon="🎯", layout="wide")
st.title("🎯 七分钟投顾组合调仓明细")
st.markdown("比对七分钟各投顾组合的持仓变化，包含份额增减、百分比、变动金额及最新总市值。")

# 设定的目标账户及别名映射
TARGET_ACCOUNTS = {
    '05898634': '七十二变',
    '07437199': '置换七十二变',
    '07044925': '七彩祥云',
    '06674620': '金如意'
}

col1, col2 = st.columns(2)
with col1:
    file_t1 = st.file_uploader("上传【前期】持仓明细表", type=["xlsx", "xls", "csv"])
with col2:
    file_t2 = st.file_uploader("上传【后期】持仓明细表", type=["xlsx", "xls", "csv"])


@st.cache_data
def load_e_account_data(file):
    """读取并清洗基金E账户导出的数据"""
    try:
        if file.name.endswith('.csv'):
            try:
                df = pd.read_csv(file, skiprows=4, encoding='utf-8', dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(file, skiprows=4, encoding='gbk', dtype=str)
        else:
            df = pd.read_excel(file, skiprows=4, dtype=str)

        df.columns = df.columns.str.strip()

        if '持有份额' in df.columns:
            df['持有份额'] = pd.to_numeric(df['持有份额'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        if '基金净值' in df.columns:
            df['基金净值'] = pd.to_numeric(df['基金净值'].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0)

        if '交易账户' in df.columns:
            df['交易账户'] = df['交易账户'].astype(str).str.strip()

        return df
    except Exception as e:
        st.error(f"读取文件 {file.name} 时出错: {e}")
        return None


if file_t1 is not None and file_t2 is not None:
    df1 = load_e_account_data(file_t1)
    df2 = load_e_account_data(file_t2)

    if df1 is not None and df2 is not None:
        required_cols = ['基金代码', '基金名称', '交易账户', '持有份额', '基金净值', '份额日期']
        if all(col in df1.columns for col in required_cols) and all(col in df2.columns for col in required_cols):

            # ---------------- 新增：计算星期几的逻辑 ----------------
            weekdays_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']


            def get_date_with_weekday(df_col, default_name):
                dates = df_col.dropna()
                if dates.empty:
                    return default_name
                date_val = dates.mode()[0]
                try:
                    # 将字符串转换为日期对象，并获取星期几的索引
                    dt = pd.to_datetime(date_val)
                    weekday_str = weekdays_cn[dt.weekday()]
                    return f"{date_val} {weekday_str}"
                except Exception:
                    return date_val


            date1_str = get_date_with_weekday(df1['份额日期'], "前期")
            date2_str = get_date_with_weekday(df2['份额日期'], "后期")

            col_prev = f'前期份额 ({date1_str})'
            col_curr = f'后期份额 ({date2_str})'
            # --------------------------------------------------------

            df1_filtered = df1[df1['交易账户'].isin(TARGET_ACCOUNTS.keys())].copy()
            df2_filtered = df2[df2['交易账户'].isin(TARGET_ACCOUNTS.keys())].copy()

            df1_filtered['账户名称'] = df1_filtered['交易账户'].map(TARGET_ACCOUNTS)
            df2_filtered['账户名称'] = df2_filtered['交易账户'].map(TARGET_ACCOUNTS)

            group_keys = ['账户名称', '基金代码', '基金名称']

            df1_clean = df1_filtered.groupby(group_keys).agg({'持有份额': 'sum', '基金净值': 'first'}).reset_index()
            df2_clean = df2_filtered.groupby(group_keys).agg({'持有份额': 'sum', '基金净值': 'first'}).reset_index()

            merged_df = pd.merge(df1_clean, df2_clean, on=group_keys, how='outer', suffixes=('_1', '_2'))

            merged_df['持有份额_1'] = merged_df['持有份额_1'].fillna(0)
            merged_df['持有份额_2'] = merged_df['持有份额_2'].fillna(0)

            merged_df.rename(columns={'持有份额_1': col_prev, '持有份额_2': col_curr}, inplace=True)

            merged_df['份额变动'] = merged_df[col_curr] - merged_df[col_prev]
            merged_df['份额变动'] = merged_df['份额变动'].round(4)


            def calc_pct(row):
                if row[col_prev] == 0 and row['份额变动'] > 0:
                    return "新买入"
                elif row[col_prev] == 0 and row['份额变动'] == 0:
                    return "0.00%"
                else:
                    return f"{(row['份额变动'] / row[col_prev]):+.2%}"


            merged_df['变动比例'] = merged_df.apply(calc_pct, axis=1)

            merged_df['参考净值'] = merged_df['基金净值_1'].fillna(merged_df['基金净值_2']).fillna(1.0)
            merged_df['估算变动金额'] = (merged_df['份额变动'] * merged_df['参考净值']).round(2)
            merged_df['最新市值'] = (merged_df[col_curr] * merged_df['参考净值']).round(2)

            display_cols = ['账户名称', '基金代码', '基金名称', col_prev, col_curr, '份额变动', '变动比例', '最新市值',
                            '估算变动金额']
            final_df = merged_df[display_cols].copy()

            account_order = list(TARGET_ACCOUNTS.values())
            final_df['账户名称'] = pd.Categorical(final_df['账户名称'], categories=account_order, ordered=True)

            changed_df = final_df[final_df['份额变动'] != 0].copy()
            changed_df = changed_df.sort_values(by=['账户名称', '估算变动金额'], ascending=[True, False]).reset_index(
                drop=True)

            st.divider()

            # ================= 账户市值与变动统计 =================
            cols = st.columns(len(TARGET_ACCOUNTS))
            for idx, (acc_code, acc_name) in enumerate(TARGET_ACCOUNTS.items()):
                acc_all = final_df[final_df['账户名称'] == acc_name]
                total_market_value = acc_all['最新市值'].sum()

                acc_changes = changed_df[changed_df['账户名称'] == acc_name]
                total_change_amount = acc_changes['估算变动金额'].sum()

                with cols[idx]:
                    st.metric(
                        label=f"💰 [{acc_name}] 最新总市值",
                        value=f"¥ {total_market_value:,.2f}",
                        delta=f"{total_change_amount:,.2f} 元 (净变动)",
                        delta_color="inverse"
                    )
                    st.caption(f"期间共 **{len(acc_changes)}** 只基金发生份额变动")

            st.divider()


            def insert_blank_rows(df):
                if df.empty: return df
                out_dfs = []
                acc_list = [acc for acc in TARGET_ACCOUNTS.values() if acc in df['账户名称'].values]

                for i, acc in enumerate(acc_list):
                    subset = df[df['账户名称'] == acc]
                    if not subset.empty:
                        out_dfs.append(subset)
                        if i < len(acc_list) - 1:
                            dummy = pd.DataFrame("", index=[0], columns=df.columns)
                            out_dfs.append(dummy)

                if out_dfs:
                    res = pd.concat(out_dfs, ignore_index=True)
                    res['账户名称'] = res['账户名称'].astype(str)
                    res['账户名称'] = res['账户名称'].replace({'nan': '', 'None': '', '<NA>': '', 'NaN': ''})
                    return res
                return df


            display_changed_df = insert_blank_rows(changed_df)
            display_all_df = insert_blank_rows(
                final_df.sort_values(by=['账户名称', '估算变动金额'], ascending=[True, False]))


            # ================= 自定义表格样式 =================
            def style_dataframe(df):
                def row_bg_color(row):
                    acc = row['账户名称']
                    if pd.isna(acc) or acc == "":
                        return [''] * len(row)

                    bg_color = ''
                    if acc == '七十二变':
                        bg_color = 'background-color: rgba(54, 162, 235, 0.12)'
                    elif acc == '置换七十二变':
                        bg_color = 'background-color: rgba(153, 102, 255, 0.12)'
                    elif acc == '七彩祥云':
                        bg_color = 'background-color: rgba(255, 159, 64, 0.12)'
                    elif acc == '金如意':
                        bg_color = 'background-color: rgba(255, 99, 132, 0.12)'
                    return [bg_color] * len(row)

                def text_color_rule(val):
                    if pd.isna(val) or val == "":
                        return ''
                    if isinstance(val, str):
                        if val == '新买入' or val.startswith('+'):
                            return 'color: #FF4B4B; font-weight: bold'  # 红色 (增长)
                        elif val.startswith('-'):
                            return 'color: #09AB3B; font-weight: bold'  # 绿色 (减少)
                        return ''
                    elif isinstance(val, (int, float)):
                        if val > 0:
                            return 'color: #FF4B4B; font-weight: bold'  # 红色 (增长)
                        elif val < 0:
                            return 'color: #09AB3B; font-weight: bold'  # 绿色 (减少)
                    return ''

                def safe_numeric_fmt(val, fmt_str):
                    if pd.isna(val) or val == "" or str(val).strip() == "" or str(val) == "nan" or str(val) == "None":
                        return ""
                    try:
                        return fmt_str.format(float(val))
                    except ValueError:
                        return str(val)

                def safe_string_fmt(val):
                    if pd.isna(val) or str(val) == "nan" or str(val) == "None":
                        return ""
                    return str(val)

                format_dict = {
                    '账户名称': safe_string_fmt,
                    '基金代码': safe_string_fmt,
                    '基金名称': safe_string_fmt,
                    '变动比例': safe_string_fmt,
                    col_prev: lambda x: safe_numeric_fmt(x, '{:,.2f}'),
                    col_curr: lambda x: safe_numeric_fmt(x, '{:,.2f}'),
                    '份额变动': lambda x: safe_numeric_fmt(x, '{:+,.2f}'),
                    '最新市值': lambda x: safe_numeric_fmt(x, '{:,.2f}'),
                    '估算变动金额': lambda x: safe_numeric_fmt(x, '{:+,.2f}')
                }

                return df.style.format(format_dict).apply(row_bg_color, axis=1).applymap(
                    text_color_rule, subset=['份额变动', '变动比例', '估算变动金额']
                )


            st.subheader(f"🎯 变动明细 (共 {len(changed_df)} 条)")
            if not display_changed_df.empty:
                st.dataframe(style_dataframe(display_changed_df), use_container_width=True, height=600, hide_index=True)
            else:
                st.success("🎉 这些关注账户在期间没有任何份额变动。")

            with st.expander("🔍 点击查看这些账户的【全部持仓对比】（含未变动）"):
                st.dataframe(
                    style_dataframe(display_all_df),
                    use_container_width=True,
                    hide_index=True
                )

        else:
            st.error("数据表格式不正确：未能找到'份额日期'或'基金净值'等列名。")
