<template>
  <div v-loading="booting">
    <PageHeader
      title="调度决策中心"
      description="基于需求预测结果测算各区域供需缺口，用匈牙利最优指派与贪心策略生成跨区运力调度方案，并对执行效果进行闭环评估。"
    >
      <template #extra>
        <el-tag type="info" effect="plain">
          <el-icon><Calendar /></el-icon>
          今天 {{ todayText }}
        </el-tag>
        <el-button :icon="Refresh" :loading="refreshing" @click="refreshCurrent">刷新当前页签</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab">
      <!-- ================================================== Tab1 供需态势 -->
      <el-tab-pane label="供需态势" name="status">
        <div class="filter-bar">
          <span class="filter-label">目标日期</span>
          <el-date-picker
            v-model="statusQuery.target_date"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
            style="width: 150px"
          />
          <span class="filter-label">目标时段</span>
          <el-select v-model="statusQuery.target_hour" style="width: 210px">
            <el-option :value="-1" label="自动选择缺口最大时段" />
            <el-option v-for="hour in 24" :key="hour" :value="hour - 1" :label="hourRange(hour - 1)" />
          </el-select>
          <el-button type="primary" :icon="Refresh" :loading="statusLoading" @click="loadStatus">
            刷新态势
          </el-button>
          <span class="text-muted hint">需求由后端按近 4 周同星期同时段均值并做趋势修正后估计</span>
        </div>

        <el-alert v-if="statusData.method" type="info" :closable="false" show-icon class="mb-16">
          <template #title>需求估计方法：{{ statusData.method }}</template>
          <template #default>
            <span v-if="statusData.auto_selected">
              未指定目标时段：后端已自动选择「可再分配运力最大」的时段
              {{ statusData.target_date }} {{ hourRange(statusData.target_hour) }}
              （可再分配量 = min(总缺口, 总盈余)，全城普遍缺车时并无可调运力）。
            </span>
            <span v-else>
              按指定时段 {{ statusData.target_date }} {{ hourRange(statusData.target_hour) }}
              计算各区域供需缺口，列表已按缺口从大到小排序。
            </span>
          </template>
        </el-alert>

        <el-row :gutter="14" class="mb-16">
          <el-col :xs="12" :md="6">
            <StatCard
              label="缺口区域数"
              :value="deficitItems.length"
              unit="个"
              icon="Warning"
              tone="red"
              :sub="`共 ${statusItems.length} 个运营区域`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="盈余区域数"
              :value="surplusItems.length"
              unit="个"
              icon="CircleCheck"
              tone="green"
              :sub="`估算可外调 ${movableVehicles} 台`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="总缺口"
              :value="totalGap"
              unit="单/小时"
              icon="TrendCharts"
              tone="orange"
              :digits="1"
              tip="缺口区域内「预测需求 − 折算运力」的正值合计，未扣除盈余区域可承接的部分"
              :sub="`缺口率 ${num(gapRatio, 1)}%`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="可调度运力"
              :value="movableVehicles"
              unit="台"
              icon="Van"
              tone="blue"
              tip="盈余区域按「−缺口 ÷ 单车小时服务能力」向下取整估算的可外调车辆数上限"
              :sub="`单车小时服务能力 ${num(serviceRate, 2)} 单`"
            />
          </el-col>
        </el-row>

        <div class="chart-card mb-16">
          <div class="chart-card__head">
            <div class="chart-card__title">区域供需平衡表</div>
            <el-tag size="small" effect="plain" type="info">
              {{ statusData.target_date }} {{ hourRange(statusData.target_hour) }}
            </el-tag>
          </div>
          <p class="chart-card__desc">
            缺口 = 预测需求 − 可用运力 × 单车小时服务能力；正值为缺口区域，负值为盈余区域。
          </p>
          <el-table
            v-loading="statusLoading"
            :data="statusItems"
            size="small"
            border
            max-height="380"
            empty-text="暂无区域供需数据"
          >
            <el-table-column label="区域名称" prop="region_name" min-width="140" show-overflow-tooltip />
            <el-table-column label="功能区" prop="region_type" width="110" show-overflow-tooltip />
            <el-table-column label="预测需求" prop="predicted_demand" align="right" width="110" sortable>
              <template #default="{ row }">
                <span class="mono">{{ num(row.predicted_demand, 1) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="可用运力" prop="current_supply" align="right" width="110" sortable>
              <template #default="{ row }">
                <span class="mono">{{ row.current_supply }} 台</span>
              </template>
            </el-table-column>
            <el-table-column label="折算运力" prop="effective_supply" align="right" width="120" sortable>
              <template #default="{ row }">
                <span class="mono">{{ num(row.effective_supply, 1) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="缺口（单/小时）" prop="gap" align="right" width="140" sortable>
              <template #default="{ row }">
                <span v-if="Number(row.gap) > 0" class="text-danger mono">+{{ num(row.gap, 1) }}</span>
                <span v-else-if="Number(row.gap) < 0" class="text-success mono">{{ num(row.gap, 1) }}</span>
                <span v-else class="text-muted mono">0.0</span>
              </template>
            </el-table-column>
            <el-table-column label="缺口等级" width="110">
              <template #default="{ row }">
                <el-tag :type="gapLevelTag(row.gap_level)" size="small" effect="light">
                  {{ row.gap_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="预期可增收" align="right" width="130">
              <template #default="{ row }">
                <span class="mono">{{ money(row.expected_revenue) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">各区域供需缺口对比</div>
            <span class="text-muted" style="font-size: 12px">红色=缺口区域，绿色=盈余区域</span>
          </div>
          <ChartBox
            :option="gapOption"
            :height="gapChartHeight"
            :loading="statusLoading"
            :empty="!statusItems.length"
            empty-text="暂无缺口数据"
          />
          <p class="chart-card__desc">
            柱体向右为缺口（需要调入运力），向左为盈余（可调出运力）；柱长表示该区域在目标时段缺或多出的服务能力（单/小时）。
          </p>
        </div>
      </el-tab-pane>

      <!-- ============================================== Tab2 生成调度方案 -->
      <el-tab-pane label="生成调度方案" name="generate">
        <div class="filter-bar">
          <span class="filter-label">目标日期</span>
          <el-date-picker
            v-model="genQuery.plan_date"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
            style="width: 150px"
          />
          <span class="filter-label">目标时段</span>
          <el-select v-model="genQuery.target_hour" style="width: 210px">
            <el-option :value="-1" label="自动选择缺口最大时段" />
            <el-option v-for="hour in 24" :key="hour" :value="hour - 1" :label="hourRange(hour - 1)" />
          </el-select>
          <span class="filter-label">调度策略</span>
          <el-radio-group v-model="genQuery.strategy">
            <el-radio-button value="hungarian">匈牙利最优指派（推荐）</el-radio-button>
            <el-radio-button value="greedy">贪心策略</el-radio-button>
          </el-radio-group>
          <span class="filter-label">是否保存方案</span>
          <el-switch v-model="genQuery.auto_save" />
          <el-button type="primary" :icon="Promotion" :loading="genLoading" @click="generatePlan">
            生成方案
          </el-button>
          <span class="text-muted hint">含供需测算、增益矩阵构造与指派求解，约需 1~5 秒</span>
        </div>

        <div v-if="genWarnings.length" class="mb-16">
          <div class="warn-head">
            <el-icon><WarningFilled /></el-icon>
            调度提示（{{ genWarnings.length }} 条，请结合实际情况判断）
          </div>
          <el-alert
            v-for="(item, index) in genWarnings"
            :key="index"
            type="warning"
            :title="item"
            :closable="false"
            show-icon
            class="mb-8"
          />
        </div>

        <template v-if="plan">
          <!-- 策略对比 -->
          <div class="chart-card mb-16">
            <div class="chart-card__head">
              <div class="chart-card__title">调度策略对比</div>
              <el-tag v-if="strategyImprove > 0" type="success" effect="dark">
                匈牙利策略多收益 {{ money(strategyImprove) }} 元
              </el-tag>
              <el-tag v-else type="info" effect="plain">两种策略结果一致</el-tag>
            </div>
            <p class="chart-card__desc">
              同一个增益矩阵下两种指派策略的求解结果对比，用于说明「最优指派 vs 启发式策略」的解质量差异。
            </p>
            <el-table :data="strategyCompare" size="small" border>
              <el-table-column label="调度策略" min-width="180">
                <template #default="{ row }">
                  <span>{{ row.strategy_label }}</span>
                  <el-tag
                    v-if="row.strategy === betterStrategy"
                    type="success"
                    size="small"
                    effect="light"
                    class="ml-4"
                  >
                    更优
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="调度车辆数（台）" align="right" width="170">
                <template #default="{ row }">
                  <span class="mono">{{ row.dispatch_count }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预期净收益（元）" align="right" width="180">
                <template #default="{ row }">
                  <span class="mono">{{ money(row.expected_gain) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="说明" min-width="220">
                <template #default="{ row }">
                  <span class="text-muted" style="font-size: 12px">
                    {{ row.strategy === 'hungarian' ? 'KM 算法求全局最大权匹配，理论上界最优' : '按边际收益递减逐次贪心选择，速度快但可能次优' }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 方案概要 -->
          <div class="chart-card mb-16">
            <div class="chart-card__head">
              <div class="chart-card__title">方案概要</div>
              <el-tag v-if="plan.id" type="success" effect="light">
                已保存 · 方案 ID {{ plan.id }}
              </el-tag>
              <el-tag v-else type="warning" effect="light">仅预览（未保存）</el-tag>
            </div>
            <el-descriptions :column="4" border size="small">
              <el-descriptions-item label="方案号">
                <span class="mono">{{ plan.plan_no }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="目标日期时段">
                {{ plan.plan_date }} {{ hourRange(plan.target_hour) }}
              </el-descriptions-item>
              <el-descriptions-item label="总需求">{{ num(plan.total_demand, 1) }} 单/小时</el-descriptions-item>
              <el-descriptions-item label="总运力">{{ num(plan.total_supply, 1) }} 单/小时</el-descriptions-item>
              <el-descriptions-item label="总缺口">{{ num(plan.total_gap, 1) }} 单/小时</el-descriptions-item>
              <el-descriptions-item label="调度车辆数">{{ plan.dispatch_count }} 台</el-descriptions-item>
              <el-descriptions-item label="预期净收益">
                <span class="text-success mono">{{ money(plan.expected_gain) }}</span> 元
              </el-descriptions-item>
              <el-descriptions-item label="创建人">{{ plan.created_by || '-' }}</el-descriptions-item>
            </el-descriptions>
            <p v-if="plan.remark" class="chart-card__desc" style="margin-top: 10px">方案说明：{{ plan.remark }}</p>
          </div>

          <!-- 调度指令表 -->
          <div class="chart-card mb-16">
            <div class="chart-card__head">
              <div class="chart-card__title">调度指令（{{ planOrders.length }} 条）</div>
              <span class="text-muted" style="font-size: 12px">按优先级与预期净收益排序</span>
            </div>
            <el-table :data="planOrders" size="small" border max-height="420" empty-text="该时段无需调度，未生成调度指令">
              <el-table-column label="调度单号" min-width="160" fixed="left">
                <template #default="{ row }">
                  <span class="mono">{{ row.dispatch_no }}</span>
                </template>
              </el-table-column>
              <el-table-column label="车牌" prop="plate_number" width="110" />
              <el-table-column label="驾驶员" width="100">
                <template #default="{ row }">{{ row.driver_name || '待绑定' }}</template>
              </el-table-column>
              <el-table-column label="调出区域 → 调入区域" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ row.from_region_name || '-' }} → <b>{{ row.to_region_name || '-' }}</b>
                </template>
              </el-table-column>
              <el-table-column label="建议时段" width="120">
                <template #default="{ row }">{{ hourRange(row.start_hour) }}</template>
              </el-table-column>
              <el-table-column label="距离(km)" align="right" width="100">
                <template #default="{ row }">
                  <span class="mono">{{ num(row.distance_km, 2) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预期收入" align="right" width="110">
                <template #default="{ row }">
                  <span class="mono">{{ money(row.expected_revenue) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预期成本" align="right" width="110">
                <template #default="{ row }">
                  <span class="mono text-muted">{{ money(row.expected_cost) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预期净收益" align="right" width="120">
                <template #default="{ row }">
                  <span class="mono text-success">{{ money(row.expected_gain) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="优先级" width="90">
                <template #default="{ row }">
                  <el-tag :type="priorityTag(row.priority)" size="small" effect="light">
                    {{ priorityText(row.priority) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="dispatchStatusTag(row.status)" size="small" effect="light">
                    {{ dispatchStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right">
                <template #default="{ row }">
                  <el-tooltip
                    :disabled="!!row.id"
                    content="该调度指令尚未入库（方案未保存），保存方案后可提交执行反馈"
                    placement="top"
                  >
                    <span>
                      <el-button link type="primary" :disabled="!row.id" @click="openFeedback(row)">
                        提交反馈
                      </el-button>
                    </span>
                  </el-tooltip>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>

        <el-empty
          v-else
          description="尚未生成调度方案：选择目标日期、时段与策略后点击「生成方案」"
        />

        <!-- 算法对比实验 -->
        <div class="chart-card mt-16">
          <div class="chart-card__head">
            <div class="chart-card__title">调度算法对比实验</div>
            <el-tag size="small" type="info" effect="plain">论文实验数据来源</el-tag>
          </div>
          <p class="chart-card__desc">
            单一时段的算例规模较小，贪心策略往往与最优解相同；只有在连续多时段与不同规模的批量算例上对比，
            才能体现匈牙利最优指派的解质量优势。
          </p>

          <!-- 实验一 -->
          <div class="exp-block">
            <div class="exp-head">
              <div class="exp-title">实验一：未来 24 小时逐时段策略对比</div>
              <div class="exp-actions">
                <el-button type="primary" plain :loading="compareLoading" @click="runCompare">
                  运行 24 小时策略对比实验
                </el-button>
                <span class="text-muted hint">逐小时构造增益矩阵并分别求解两种策略，约需数秒到数十秒</span>
              </div>
            </div>

            <template v-if="compareData">
              <el-descriptions :column="4" border size="small" class="mb-16">
                <el-descriptions-item label="评估时段数">
                  {{ compareData.evaluated_hours }} 小时
                </el-descriptions-item>
                <el-descriptions-item label="匈牙利更优时段">
                  <span class="text-success">{{ compareData.better_hours }}</span> 小时
                </el-descriptions-item>
                <el-descriptions-item label="两策略持平时段">
                  {{ compareData.tie_hours }} 小时
                </el-descriptions-item>
                <el-descriptions-item label="累计提升">
                  <span class="text-success mono">{{ money(compareData.improve) }}</span> 元
                  <span v-if="compareData.improve_pct !== null && compareData.improve_pct !== undefined" class="text-muted">
                    （{{ num(compareData.improve_pct, 2) }}%）
                  </span>
                </el-descriptions-item>
              </el-descriptions>

              <el-row :gutter="14">
                <el-col :xs="24" :md="10">
                  <el-table :data="compareTotals" size="small" border>
                    <el-table-column label="调度策略" prop="label" min-width="140" />
                    <el-table-column label="总调度车辆数（台）" align="right" width="160">
                      <template #default="{ row }">
                        <span class="mono">{{ row.count }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="总预期净收益（元）" align="right" width="170">
                      <template #default="{ row }">
                        <span class="mono">{{ money(row.gain) }}</span>
                      </template>
                    </el-table-column>
                  </el-table>
                  <p class="chart-card__desc" style="margin-top: 10px">
                    匈牙利最优指派在 {{ compareData.better_hours }} 个时段取得更高收益、{{ compareData.tie_hours }} 个时段与贪心持平，
                    累计多收益 {{ money(compareData.improve) }} 元，说明最优指派在高缺口、多区域并发时优势更明显。
                  </p>
                </el-col>
                <el-col :xs="24" :md="14">
                  <ChartBox
                    :option="compareChartOption"
                    :height="280"
                    :empty="!compareRows.length"
                    empty-text="暂无逐时段对比数据"
                  />
                </el-col>
              </el-row>

              <el-table :data="compareRows" size="small" border max-height="320" class="mt-16">
                <el-table-column label="时刻" min-width="130">
                  <template #default="{ row }">
                    <span class="mono">{{ shortTime(row.time) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="缺口（单/小时）" align="right" width="130">
                  <template #default="{ row }">
                    <span class="mono text-danger">{{ num(row.total_gap, 1) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="缺口区域数" align="right" width="110">
                  <template #default="{ row }">{{ row.deficit_regions }}</template>
                </el-table-column>
                <el-table-column label="盈余区域数" align="right" width="110">
                  <template #default="{ row }">{{ row.surplus_regions }}</template>
                </el-table-column>
                <el-table-column label="贪心收益（元）" align="right" width="140">
                  <template #default="{ row }">
                    <span class="mono">{{ money(row.greedy_gain) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="匈牙利收益（元）" align="right" width="150">
                  <template #default="{ row }">
                    <span class="mono">{{ money(row.hungarian_gain) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="提升（元）" align="right" width="120">
                  <template #default="{ row }">
                    <span class="mono" :class="Number(row.improve) > 0 ? 'text-success' : 'text-muted'">
                      {{ signed(row.improve, 2) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="提升幅度" align="right" width="110">
                  <template #default="{ row }">
                    <span v-if="row.improve_pct === null || row.improve_pct === undefined" class="text-muted">—</span>
                    <span v-else class="mono">{{ num(row.improve_pct, 2) }}%</span>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <el-empty v-else description="尚未运行，点击上方按钮开始实验" :image-size="60" />
          </div>

          <el-divider />

          <!-- 实验二 -->
          <div class="exp-block">
            <div class="exp-head">
              <div class="exp-title">实验二：随机算例基准实验（不同算例规模）</div>
              <div class="exp-actions">
                <el-button type="primary" plain :loading="benchmarkLoading" @click="runBenchmark">
                  运行随机算例基准实验
                </el-button>
                <span class="text-muted hint">每个规模生成 200 组随机算例并统计解质量与耗时，约需数秒到数十秒</span>
              </div>
            </div>

            <template v-if="benchmarkData">
              <p class="chart-card__desc">
                收益矩阵按「调度收入 − 距离成本」生成，随机种子 {{ benchmarkData.seed }}，
                距离成本系数 {{ benchmarkData.cost_per_km }} 元/km；同一算例分别用两种策略求解并对比。
              </p>
              <el-table :data="benchmarkData.results" size="small" border>
                <el-table-column label="算例规模" align="right" width="100" fixed="left">
                  <template #default="{ row }">{{ row.size }} × {{ row.size }}</template>
                </el-table-column>
                <el-table-column label="算例数" align="right" width="90">
                  <template #default="{ row }">{{ row.instances }}</template>
                </el-table-column>
                <el-table-column label="贪心均值（元）" align="right" min-width="140">
                  <template #default="{ row }">
                    <span class="mono">{{ money(row.greedy_mean_gain) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="匈牙利均值（元）" align="right" min-width="150">
                  <template #default="{ row }">
                    <span class="mono">{{ money(row.hungarian_mean_gain) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="平均提升（元）" align="right" min-width="140">
                  <template #default="{ row }">
                    <span class="mono text-success">{{ money(row.mean_improve) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="提升%" align="right" width="100">
                  <template #default="{ row }">
                    <span v-if="row.improve_pct === null || row.improve_pct === undefined" class="text-muted">—</span>
                    <span v-else class="mono">{{ num(row.improve_pct, 2) }}%</span>
                  </template>
                </el-table-column>
                <el-table-column label="匈牙利更优算例数" align="right" width="160">
                  <template #default="{ row }">
                    <span class="mono">{{ row.hungarian_better_instances }}</span>
                    <span class="text-muted" style="font-size: 12px">（{{ num(row.better_ratio, 1) }}%）</span>
                  </template>
                </el-table-column>
                <el-table-column label="持平算例数" align="right" width="120">
                  <template #default="{ row }">
                    <span class="mono">{{ row.tie_instances }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="贪心耗时(ms)" align="right" width="130">
                  <template #default="{ row }">
                    <span class="mono text-muted">{{ num(row.greedy_avg_ms, 3) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="匈牙利耗时(ms)" align="right" width="140">
                  <template #default="{ row }">
                    <span class="mono text-muted">{{ num(row.hungarian_avg_ms, 3) }}</span>
                  </template>
                </el-table-column>
              </el-table>
              <ChartBox
                :option="benchmarkChartOption"
                :height="300"
                :empty="!benchmarkResults.length"
                empty-text="暂无基准实验结果"
                class="mt-16"
              />
              <p class="chart-card__desc">
                随着算例规模增大，匈牙利最优指派相对贪心策略的平均收益提升更稳定；
                其代价是求解耗时随规模增长更快，实际调度中可按算例规模在「最优性」与「响应速度」之间取舍。
              </p>
            </template>
            <el-empty v-else description="尚未运行，点击上方按钮开始实验" :image-size="60" />
          </div>
        </div>
      </el-tab-pane>

      <!-- ============================================== Tab3 调度方案管理 -->
      <el-tab-pane label="调度方案管理" name="plans">
        <div class="filter-bar">
          <span class="filter-label">调度日期</span>
          <el-date-picker
            v-model="planQuery.range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
          <span class="filter-label">方案状态</span>
          <el-select v-model="planQuery.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option
              v-for="(item, key) in PLAN_STATUS"
              :key="key"
              :value="Number(key)"
              :label="item.text"
            />
          </el-select>
          <el-button type="primary" :icon="Search" :loading="plansLoading" @click="searchPlans">查询</el-button>
          <el-button :icon="RefreshLeft" @click="resetPlanQuery">重置</el-button>
        </div>

        <div class="table-card">
          <div class="table-toolbar">
            <div class="chart-card__title">调度方案列表（共 {{ planPager.total }} 条）</div>
            <span class="text-muted" style="font-size: 12px">已下发 / 执行中的方案不允许删除</span>
          </div>
          <el-table v-loading="plansLoading" :data="plans" size="small" border empty-text="暂无调度方案">
            <el-table-column label="方案号" min-width="160" fixed="left">
              <template #default="{ row }">
                <span class="mono">{{ row.plan_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="调度日期" prop="plan_date" width="110" />
            <el-table-column label="目标时段" width="130">
              <template #default="{ row }">{{ hourRange(row.target_hour) }}</template>
            </el-table-column>
            <el-table-column label="策略" width="130">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="row.strategy === 'hungarian' ? 'primary' : 'info'">
                  {{ strategyText(row.strategy) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="调度车辆数" align="right" width="110">
              <template #default="{ row }">
                <span class="mono">{{ row.dispatch_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已完成数" align="right" width="100">
              <template #default="{ row }">
                <span class="mono">{{ row.done_count ?? 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="总缺口" align="right" width="100">
              <template #default="{ row }">
                <span class="mono">{{ num(row.total_gap, 1) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预期净收益" align="right" width="120">
              <template #default="{ row }">
                <span class="mono text-success">{{ money(row.expected_gain) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="planStatusTag(row.status)" size="small" effect="light">
                  {{ planStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建人" prop="created_by" width="100" />
            <el-table-column label="创建时间" width="150">
              <template #default="{ row }">{{ formatDateTime(row.create_time, true) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openPlanDetail(row)">详情</el-button>
                <el-dropdown @command="(command) => changePlanStatus(row, command)">
                  <el-button link type="primary">
                    变更状态<el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        v-for="(item, key) in PLAN_STATUS"
                        :key="key"
                        :command="Number(key)"
                        :disabled="Number(key) === row.status"
                      >
                        {{ item.text }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button link type="danger" @click="confirmRemovePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-bar">
            <el-pagination
              v-model:current-page="planPager.page"
              v-model:page-size="planPager.page_size"
              :total="planPager.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="loadPlans"
              @current-change="loadPlans"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- ========================================== Tab4 执行与效果评估 -->
      <el-tab-pane label="执行与效果评估" name="execute">
        <el-row :gutter="14" class="mb-16">
          <el-col :xs="12" :md="6">
            <StatCard
              label="调度方案数"
              :value="statistics.plan_count ?? 0"
              unit="个"
              icon="Guide"
              tone="blue"
              :sub="`统计区间：近 ${statistics.days ?? 30} 天`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="调度单数"
              :value="statistics.order_count ?? 0"
              unit="条"
              icon="Tickets"
              tone="cyan"
              :sub="`待执行/执行中 ${statistics.pending_count ?? 0} 条`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="预期净收益"
              :value="statistics.expected_gain ?? 0"
              unit="元"
              icon="Money"
              tone="green"
              :digits="2"
              :sub="`已完成 ${statistics.done_count ?? 0} 条 / 已拒绝 ${statistics.rejected_count ?? 0} 条`"
            />
          </el-col>
          <el-col :xs="12" :md="6">
            <StatCard
              label="调度完成率"
              :value="statistics.done_ratio ?? 0"
              unit="%"
              icon="CircleCheck"
              tone="orange"
              :digits="1"
              tip="已完成调度单数 ÷ 全部调度单数"
              :sub="`基于近 ${statistics.days ?? 30} 天的调度指令统计`"
            />
          </el-col>
        </el-row>

        <el-row :gutter="14" class="mb-16">
          <el-col :xs="24" :md="12">
            <div class="chart-card" v-loading="statLoading">
              <div class="chart-card__head">
                <div class="chart-card__title">调度方案按策略分布</div>
                <span class="text-muted" style="font-size: 12px">单位：方案数</span>
              </div>
              <ChartBox
                :option="strategyPieOption"
                :height="240"
                :loading="statLoading"
                :empty="!strategyPie.length"
                empty-text="暂无调度方案"
              />
            </div>
          </el-col>
          <el-col :xs="24" :md="12">
            <div class="chart-card" v-loading="statLoading">
              <div class="chart-card__head">
                <div class="chart-card__title">调度单按状态分布</div>
                <span class="text-muted" style="font-size: 12px">单位：调度单数</span>
              </div>
              <ChartBox
                :option="statusPieOption"
                :height="240"
                :loading="statLoading"
                :empty="!statusPie.length"
                empty-text="暂无调度指令"
              />
            </div>
          </el-col>
        </el-row>

        <div class="table-card mb-16">
          <div class="table-toolbar">
            <div class="chart-card__title">调度执行列表（共 {{ orderPager.total }} 条）</div>
            <div class="toolbar-filters">
              <el-select v-model="orderQuery.plan_id" placeholder="全部方案" clearable style="width: 230px">
                <el-option
                  v-for="item in planOptions"
                  :key="item.id"
                  :value="item.id"
                  :label="`${item.plan_no} · ${item.plan_date} ${hourRange(item.target_hour)}`"
                />
              </el-select>
              <el-select v-model="orderQuery.status" placeholder="全部状态" clearable style="width: 140px">
                <el-option
                  v-for="(item, key) in DISPATCH_STATUS"
                  :key="key"
                  :value="Number(key)"
                  :label="item.text"
                />
              </el-select>
              <el-button type="primary" :icon="Search" :loading="ordersLoading" @click="searchOrders">
                查询
              </el-button>
            </div>
          </div>
          <el-table v-loading="ordersLoading" :data="orders" size="small" border empty-text="暂无调度指令">
            <el-table-column label="调度单号" min-width="160" fixed="left">
              <template #default="{ row }">
                <span class="mono">{{ row.dispatch_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="车牌" prop="plate_number" width="110" />
            <el-table-column label="驾驶员" width="100">
              <template #default="{ row }">{{ row.driver_name || '待绑定' }}</template>
            </el-table-column>
            <el-table-column label="调出区域 → 调入区域" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.from_region_name || '-' }} → <b>{{ row.to_region_name || '-' }}</b>
              </template>
            </el-table-column>
            <el-table-column label="建议时段" width="120">
              <template #default="{ row }">{{ hourRange(row.start_hour) }}</template>
            </el-table-column>
            <el-table-column label="距离(km)" align="right" width="100">
              <template #default="{ row }">
                <span class="mono">{{ num(row.distance_km, 2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预期收入" align="right" width="110">
              <template #default="{ row }">
                <span class="mono">{{ money(row.expected_revenue) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预期成本" align="right" width="110">
              <template #default="{ row }">
                <span class="mono text-muted">{{ money(row.expected_cost) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预期净收益" align="right" width="120">
              <template #default="{ row }">
                <span class="mono text-success">{{ money(row.expected_gain) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="priorityTag(row.priority)" size="small" effect="light">
                  {{ priorityText(row.priority) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="dispatchStatusTag(row.status)" size="small" effect="light">
                  {{ row.status_text || dispatchStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="执行时间" width="150">
              <template #default="{ row }">
                <span v-if="!row.executed_time" class="text-muted">—</span>
                <span v-else>{{ formatDateTime(row.executed_time, true) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="反馈" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="!row.feedback" class="text-muted">—</span>
                <span v-else>{{ row.feedback }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-tooltip
                  :disabled="row.status === 0 || row.status === 1"
                  content="已完成 / 已拒绝 / 已取消的调度单不能重复提交反馈"
                  placement="top"
                >
                  <span>
                    <el-button
                      link
                      type="primary"
                      :disabled="row.status === 2 || row.status === 3 || row.status === 4"
                      @click="openFeedback(row)"
                    >
                      提交反馈
                    </el-button>
                  </span>
                </el-tooltip>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-bar">
            <el-pagination
              v-model:current-page="orderPager.page"
              v-model:page-size="orderPager.page_size"
              :total="orderPager.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="loadOrders"
              @current-change="loadOrders"
            />
          </div>
        </div>

        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">调度效果评估</div>
            <div class="toolbar-filters">
              <el-select
                v-model="effectPlanId"
                placeholder="选择已完成的调度方案"
                clearable
                style="width: 280px"
                filterable
              >
                <el-option
                  v-for="item in effectPlans"
                  :key="item.id"
                  :value="item.id"
                  :label="`${item.plan_no} · ${item.plan_date} ${hourRange(item.target_hour)}`"
                />
              </el-select>
              <el-button type="primary" :loading="effectLoading" @click="loadEffect">开始评估</el-button>
              <span class="text-muted hint">逐条比对目标区域实际收入与前 3 周同星期同时段基线，约需数秒</span>
            </div>
          </div>
          <p class="chart-card__desc">
            实际增收 =（目标区域该时段实际收入 − 前 3 周同星期同时段基线收入）÷ 同区域调度车辆数 − 调度成本；
            准确率 = 100 − |实际净收益 − 按完成比例折算的预期净收益| ÷ 预期净收益，反映预期收益测算的可信度。
          </p>

          <el-empty
            v-if="!effectData"
            description="请选择已完成的调度方案后点击「开始评估」"
            :image-size="70"
          />
          <template v-else>
            <el-row :gutter="14" class="mb-16">
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard label="调度单数" :value="effectData.dispatch_count" unit="条" icon="Tickets" tone="blue" />
              </el-col>
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard label="完成数" :value="effectData.done_count" unit="条" icon="CircleCheck" tone="green" />
              </el-col>
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard
                  label="完成率"
                  :value="effectData.done_ratio"
                  unit="%"
                  icon="DataLine"
                  tone="cyan"
                  :digits="2"
                />
              </el-col>
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard
                  label="预期净收益"
                  :value="effectData.expected_gain"
                  unit="元"
                  icon="Money"
                  tone="orange"
                  :digits="2"
                />
              </el-col>
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard
                  label="实际净收益"
                  :value="effectData.actual_gain"
                  unit="元"
                  icon="TrendCharts"
                  tone="purple"
                  :digits="2"
                  :sub="`偏差 ${signed(effectData.actual_gain - effectData.expected_gain, 2)} 元`"
                />
              </el-col>
              <el-col :xs="12" :sm="8" :md="4">
                <StatCard
                  label="测算准确率"
                  :value="effectData.accuracy ?? 0"
                  unit="%"
                  icon="Aim"
                  tone="green"
                  :digits="2"
                  tip="实际净收益与按完成比例折算的预期净收益之间的接近程度"
                />
              </el-col>
            </el-row>

            <el-row :gutter="14">
              <el-col :xs="24" :md="13">
                <el-table :data="effectData.detail" size="small" border max-height="340" empty-text="暂无调度单明细">
                  <el-table-column label="调度单号" min-width="150">
                    <template #default="{ row }">
                      <span class="mono">{{ row.dispatch_no }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="目标区域" prop="to_region_name" min-width="110" show-overflow-tooltip />
                  <el-table-column label="状态" width="90">
                    <template #default="{ row }">
                      <el-tag :type="dispatchStatusTag(row.status)" size="small" effect="light">
                        {{ dispatchStatusText(row.status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="预期净收益" align="right" width="120">
                    <template #default="{ row }">
                      <span class="mono">{{ money(row.expected_gain) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="实际收入" align="right" width="110">
                    <template #default="{ row }">
                      <span class="mono">{{ money(row.actual_income) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="基线收入" align="right" width="110">
                    <template #default="{ row }">
                      <span class="mono text-muted">{{ money(row.baseline_income) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="实际增收" align="right" width="120">
                    <template #default="{ row }">
                      <span class="mono" :class="Number(row.actual_gain) >= 0 ? 'text-success' : 'text-danger'">
                        {{ money(row.actual_gain) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="距离(km)" align="right" width="100">
                    <template #default="{ row }">
                      <span class="mono">{{ num(row.distance_km, 2) }}</span>
                    </template>
                  </el-table-column>
                </el-table>
              </el-col>
              <el-col :xs="24" :md="11">
                <ChartBox
                  :option="effectOption"
                  :height="340"
                  :empty="!effectDetail.length"
                  empty-text="暂无评估明细"
                />
              </el-col>
            </el-row>
            <p class="chart-card__desc">
              柱体为各调度单的预期净收益与实际增收对比：实际增收低于预期说明调度车辆未能充分承接增量订单，
              或目标区域本身需求被高估，可据此调整调度规模与目标区域选择。
            </p>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ------------------------------------------------ 提交反馈对话框 -->
    <el-dialog v-model="feedbackVisible" title="提交调度执行反馈" width="520px">
      <el-form label-width="90px">
        <el-form-item label="调度单号">
          <span class="mono">{{ feedbackRow.dispatch_no || '-' }}</span>
        </el-form-item>
        <el-form-item label="目标区域">
          <span>{{ feedbackRow.from_region_name || '-' }} → {{ feedbackRow.to_region_name || '-' }}</span>
        </el-form-item>
        <el-form-item label="执行状态">
          <el-radio-group v-model="feedbackForm.status">
            <el-radio v-for="item in FEEDBACK_STATUS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="反馈说明">
          <el-input
            v-model="feedbackForm.feedback"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="例如：车辆已到达目标区域，高峰时段多承接 5 单，收入符合预期"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" :loading="feedbackLoading" @click="submitFeedback">提交反馈</el-button>
      </template>
    </el-dialog>

    <!-- -------------------------------------------------- 方案详情抽屉 -->
    <el-drawer v-model="planDetailVisible" :title="planDetailTitle" size="58%">
      <div v-loading="planDetailLoading">
        <template v-if="planDetailData">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="方案号">
              <span class="mono">{{ planDetailData.plan_no }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="目标日期时段">
              {{ planDetailData.plan_date }} {{ hourRange(planDetailData.target_hour) }}
            </el-descriptions-item>
            <el-descriptions-item label="调度策略">{{ strategyText(planDetailData.strategy) }}</el-descriptions-item>
            <el-descriptions-item label="方案状态">
              <el-tag :type="planStatusTag(planDetailData.status)" size="small" effect="light">
                {{ planStatusText(planDetailData.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="总需求">{{ num(planDetailData.total_demand, 1) }} 单/小时</el-descriptions-item>
            <el-descriptions-item label="总运力">{{ num(planDetailData.total_supply, 1) }} 单/小时</el-descriptions-item>
            <el-descriptions-item label="总缺口">{{ num(planDetailData.total_gap, 1) }} 单/小时</el-descriptions-item>
            <el-descriptions-item label="调度车辆数">
              {{ planDetailData.dispatch_count }} 台（已完成 {{ planDetailData.done_count ?? 0 }} 条）
            </el-descriptions-item>
            <el-descriptions-item label="预期净收益">
              <span class="text-success mono">{{ money(planDetailData.expected_gain) }}</span> 元
            </el-descriptions-item>
            <el-descriptions-item label="创建信息">
              {{ planDetailData.created_by || '-' }} · {{ formatDateTime(planDetailData.create_time, true) }}
            </el-descriptions-item>
          </el-descriptions>
          <p v-if="planDetailData.remark" class="chart-card__desc" style="margin-top: 10px">
            {{ planDetailData.remark }}
          </p>

          <div class="chart-card__head mt-16">
            <div class="chart-card__title">调度单明细（{{ planDetailOrders.length }} 条）</div>
          </div>
          <el-table :data="planDetailOrders" size="small" border max-height="420" empty-text="暂无调度单">
            <el-table-column label="调度单号" min-width="150">
              <template #default="{ row }">
                <span class="mono">{{ row.dispatch_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="车牌" prop="plate_number" width="110" />
            <el-table-column label="驾驶员" width="100">
              <template #default="{ row }">{{ row.driver_name || '待绑定' }}</template>
            </el-table-column>
            <el-table-column label="调出 → 调入" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.from_region_name || '-' }} → <b>{{ row.to_region_name || '-' }}</b>
              </template>
            </el-table-column>
            <el-table-column label="时段" width="120">
              <template #default="{ row }">{{ hourRange(row.start_hour) }}</template>
            </el-table-column>
            <el-table-column label="预期净收益" align="right" width="120">
              <template #default="{ row }">
                <span class="mono text-success">{{ money(row.expected_gain) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="dispatchStatusTag(row.status)" size="small" effect="light">
                  {{ row.status_text || dispatchStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="执行时间" width="150">
              <template #default="{ row }">
                <span v-if="!row.executed_time" class="text-muted">—</span>
                <span v-else>{{ formatDateTime(row.executed_time, true) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="反馈信息" min-width="200">
              <template #default="{ row }">
                <span v-if="!row.feedback" class="text-muted">—</span>
                <span v-else>{{ row.feedback }}</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 调度决策中心：
 * 1) 供需态势：区域级供需缺口测算与可视化；
 * 2) 生成调度方案：匈牙利最优指派 / 贪心策略求解 + 算法对比实验；
 * 3) 方案管理：查询、详情、状态流转与删除；
 * 4) 执行与效果评估：调度单反馈、方案效果闭环评估与调度统计。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Promotion, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import ChartBox from '../components/ChartBox.vue';
import { dispatchApi } from '../api';
import {
  DISPATCH_STATUS,
  PLAN_STATUS,
  formatDate,
  formatDateTime,
  money,
  recentRange,
} from '../utils/format';

/* -------------------------------------------------------------- 字典常量 */
const STRATEGY_TEXT = { greedy: '贪心策略', hungarian: '匈牙利最优指派' };
const GAP_LEVEL_TAG = { 严重缺口: 'danger', 明显缺口: 'warning', 轻微缺口: 'info', 运力盈余: 'success' };
const PRIORITY_TAG = { 1: 'danger', 2: 'warning', 3: 'info' };
const PRIORITY_TEXT = { 1: '高', 2: '中', 3: '低' };
const FEEDBACK_STATUS = [
  { value: 1, label: '执行中' },
  { value: 2, label: '已完成' },
  { value: 3, label: '已拒绝' },
  { value: 4, label: '已取消' },
];
const PIE_COLORS = ['#2b6de5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const todayText = formatDate(new Date());

/* ------------------------------------------------------------ 通用小工具 */
function num(value, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—';
}

function signed(value, digits = 2) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '—';
  return `${parsed > 0 ? '+' : ''}${parsed.toFixed(digits)}`;
}

/** 后端返回 ISO 时间字符串，直接截取为 MM-DD HH:mm，避免时区解析差异 */
function shortTime(value) {
  if (!value) return '-';
  return String(value).replace('T', ' ').slice(5, 16);
}

function pad(value) {
  return String(value).padStart(2, '0');
}

/** 目标时段文案：08:00-09:00 */
function hourRange(hour) {
  const value = Number(hour);
  if (!Number.isFinite(value)) return '-';
  return `${pad(value)}:00-${pad((value + 1) % 24)}:00`;
}

/** 过滤掉 null / undefined / 空串，避免 FastAPI 收到无效查询参数 */
function pruneParams(source) {
  const output = {};
  Object.keys(source).forEach((key) => {
    const value = source[key];
    if (value === null || value === undefined || value === '') return;
    output[key] = value;
  });
  return output;
}

function strategyText(value) {
  return STRATEGY_TEXT[value] || value || '-';
}

function gapLevelTag(level) {
  return GAP_LEVEL_TAG[level] || 'info';
}

function priorityTag(value) {
  return PRIORITY_TAG[Number(value)] || 'info';
}

function priorityText(value) {
  return PRIORITY_TEXT[Number(value)] || '低';
}

function dispatchStatusTag(value) {
  const item = DISPATCH_STATUS[Number(value)];
  return item ? item.type : 'info';
}

function dispatchStatusText(value) {
  const item = DISPATCH_STATUS[Number(value)];
  return item ? item.text : '未知';
}

function planStatusTag(value) {
  const item = PLAN_STATUS[Number(value)];
  return item ? item.type : 'info';
}

function planStatusText(value) {
  const item = PLAN_STATUS[Number(value)];
  return item ? item.text : '未知';
}

/* -------------------------------------------------------------- 页面状态 */
const activeTab = ref('status');
const booting = ref(false);
const refreshing = ref(false);

/* -------------------------------------------------------- Tab1 供需态势 */
const statusQuery = ref({ target_date: formatDate(new Date()), target_hour: -1 });
const statusData = ref({ items: [], method: '', auto_selected: false, target_hour: null, target_date: '' });
const statusLoading = ref(false);

const statusItems = computed(() => statusData.value.items || []);
const deficitItems = computed(() => statusItems.value.filter((item) => Number(item.gap) > 0));
const surplusItems = computed(() => statusItems.value.filter((item) => Number(item.gap) < 0));
const totalGap = computed(() =>
  deficitItems.value.reduce((sum, item) => sum + Number(item.gap || 0), 0)
);
const totalDemand = computed(() =>
  statusItems.value.reduce((sum, item) => sum + Number(item.predicted_demand || 0), 0)
);
const gapRatio = computed(() => (totalDemand.value > 0 ? (totalGap.value / totalDemand.value) * 100 : 0));
/** 单车小时服务能力：由后端返回的「折算运力 ÷ 可用运力」反推，用于估算可外调车辆数 */
const serviceRate = computed(() => {
  const item = statusItems.value.find(
    (row) => Number(row.current_supply) > 0 && Number(row.effective_supply) > 0
  );
  return item ? Number(item.effective_supply) / Number(item.current_supply) : 0;
});
const movableVehicles = computed(() => {
  const rate = serviceRate.value;
  if (!rate) return 0;
  return surplusItems.value.reduce(
    (sum, item) => sum + Math.floor(Math.abs(Number(item.gap)) / rate),
    0
  );
});
const gapChartHeight = computed(() =>
  Math.max(280, Math.min(620, statusItems.value.length * 26 + 90))
);

const gapOption = computed(() => {
  const list = [...statusItems.value].sort((a, b) => Number(a.gap) - Number(b.gap));
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        if (!params || !params.length) return '';
        const item = list[params[0].dataIndex];
        if (!item) return '';
        const gap = Number(item.gap);
        const color = gap > 0 ? '#ef4444' : '#10b981';
        return [
          `<div style="font-weight:600;margin-bottom:4px">${item.region_name}（${item.region_type || '-'}）</div>`,
          `<div>预测需求：${num(item.predicted_demand, 1)} 单/小时</div>`,
          `<div>可用运力：${item.current_supply} 台 / 折算 ${num(item.effective_supply, 1)} 单</div>`,
          `<div>${gap > 0 ? '缺口' : '盈余'}：<b style="color:${color}">${num(Math.abs(gap), 1)} 单/小时</b></div>`,
          `<div>缺口等级：${item.gap_level}</div>`,
          `<div>预期可增收：${money(item.expected_revenue)} 元</div>`,
        ].join('');
      },
    },
    grid: { left: 10, right: 70, top: 16, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      name: '缺口(单/小时)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.region_name),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563' },
    },
    series: [
      {
        name: '供需缺口',
        type: 'bar',
        barMaxWidth: 16,
        data: list.map((item) => {
          const value = Number(item.gap);
          return { value, label: { position: value >= 0 ? 'right' : 'left' } };
        }),
        itemStyle: {
          color: (params) => (Number(params.value) >= 0 ? '#ef4444' : '#10b981'),
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          formatter: (params) => num(params.value, 1),
          color: '#6b7280',
          fontSize: 11,
        },
      },
    ],
  };
});

async function loadStatus() {
  statusLoading.value = true;
  try {
    statusData.value = await dispatchApi.regionStatus(
      pruneParams({
        target_date: statusQuery.value.target_date || null,
        target_hour: statusQuery.value.target_hour === -1 ? null : statusQuery.value.target_hour,
      })
    );
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    statusLoading.value = false;
  }
}

/* ---------------------------------------------------- Tab2 生成调度方案 */
const genQuery = ref({
  plan_date: formatDate(new Date()),
  target_hour: -1,
  strategy: 'hungarian',
  auto_save: true,
});
const genLoading = ref(false);
const genResult = ref(null);

const plan = computed(() => (genResult.value && genResult.value.plan) || null);
const planOrders = computed(() => (plan.value && plan.value.orders) || []);
const genWarnings = computed(() => (genResult.value && genResult.value.warnings) || []);
const strategyCompare = computed(() => (genResult.value && genResult.value.strategy_compare) || []);
const betterStrategy = computed(() => {
  const list = strategyCompare.value;
  if (list.length < 2) return '';
  return list.reduce((best, item) =>
    Number(item.expected_gain) > Number(best.expected_gain) ? item : best
  ).strategy;
});
const strategyImprove = computed(() => {
  const greedy = strategyCompare.value.find((item) => item.strategy === 'greedy');
  const hungarian = strategyCompare.value.find((item) => item.strategy === 'hungarian');
  if (!greedy || !hungarian) return 0;
  return Number(hungarian.expected_gain || 0) - Number(greedy.expected_gain || 0);
});

async function generatePlan() {
  genLoading.value = true;
  try {
    const data = await dispatchApi.generate({
      plan_date: genQuery.value.plan_date,
      target_hour: genQuery.value.target_hour === -1 ? null : genQuery.value.target_hour,
      strategy: genQuery.value.strategy,
      auto_save: genQuery.value.auto_save,
    });
    genResult.value = data;
    // 方案已落库时回读一次明细，拿到调度单真实 ID 与驾驶员信息，便于直接提交执行反馈
    if (data.plan && data.plan.id) {
      try {
        const detail = await dispatchApi.planDetail(data.plan.id);
        if (detail) genResult.value = { ...data, plan: detail };
      } catch (error) {
        /* 回读失败时保留生成结果 */
      }
    }
    if (data.plan && data.plan.dispatch_count) {
      ElMessage.success(
        `已生成调度方案 ${data.plan.plan_no}：调度 ${data.plan.dispatch_count} 台车，预期净收益 ${money(
          data.plan.expected_gain
        )} 元`
      );
    } else {
      ElMessage.warning('目标时段没有可执行的调度指令，请查看提示信息');
    }
    loadPlanOptions();
    loadEffectPlans();
    plansLoaded.value = false;
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    genLoading.value = false;
  }
}

/* ------------------------------------------------ Tab2 算法对比实验数据 */
const compareLoading = ref(false);
const compareData = ref(null);
const benchmarkLoading = ref(false);
const benchmarkData = ref(null);

const compareRows = computed(() => (compareData.value && compareData.value.rows) || []);
const compareTotals = computed(() => {
  const totals = (compareData.value && compareData.value.totals) || {};
  return [
    {
      label: '贪心策略',
      count: (totals.greedy && totals.greedy.dispatch_count) || 0,
      gain: (totals.greedy && totals.greedy.expected_gain) || 0,
    },
    {
      label: '匈牙利最优指派',
      count: (totals.hungarian && totals.hungarian.dispatch_count) || 0,
      gain: (totals.hungarian && totals.hungarian.expected_gain) || 0,
    },
  ];
});
const benchmarkResults = computed(() => (benchmarkData.value && benchmarkData.value.results) || []);

const compareChartOption = computed(() => {
  const rows = compareRows.value;
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['贪心策略', '匈牙利最优指派'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((item) => shortTime(item.time)),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7280',
        fontSize: 10,
        interval: Math.max(0, Math.ceil(rows.length / 8) - 1),
      },
    },
    yAxis: {
      type: 'value',
      name: '预期净收益(元)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '贪心策略',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: rows.map((item) => item.greedy_gain),
        itemStyle: { color: '#f59e0b' },
      },
      {
        name: '匈牙利最优指派',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: rows.map((item) => item.hungarian_gain),
        itemStyle: { color: '#2b6de5' },
        areaStyle: { color: 'rgba(43,109,229,0.10)' },
      },
    ],
  };
});

const benchmarkChartOption = computed(() => {
  const list = benchmarkResults.value;
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['贪心策略', '匈牙利最优指派'], right: 0, top: 0 },
    grid: { left: 10, right: 20, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: list.map((item) => `规模 ${item.size}`),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '平均收益(元)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '贪心策略',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.greedy_mean_gain),
        itemStyle: { color: '#f59e0b' },
      },
      {
        name: '匈牙利最优指派',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.hungarian_mean_gain),
        itemStyle: { color: '#2b6de5' },
      },
    ],
  };
});

async function runCompare() {
  compareLoading.value = true;
  try {
    compareData.value = await dispatchApi.strategyCompare({ hours: 24 });
    ElMessage.success(
      `对比实验完成：共评估 ${compareData.value.evaluated_hours} 个时段，匈牙利策略累计多收益 ${money(
        compareData.value.improve
      )} 元`
    );
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    compareLoading.value = false;
  }
}

async function runBenchmark() {
  benchmarkLoading.value = true;
  try {
    benchmarkData.value = await dispatchApi.strategyBenchmark({ instances: 200 });
    ElMessage.success(`基准实验完成：共 ${benchmarkResults.value.length} 个算例规模 × 200 组随机算例`);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    benchmarkLoading.value = false;
  }
}

/* -------------------------------------------------- Tab3 调度方案管理 */
const planQuery = ref({ range: recentRange(30), status: null });
const plans = ref([]);
const plansLoading = ref(false);
const plansLoaded = ref(false);
const planPager = ref({ page: 1, page_size: 10, total: 0 });

const planDetailVisible = ref(false);
const planDetailLoading = ref(false);
const planDetailData = ref(null);
const planDetailOrders = computed(() => (planDetailData.value && planDetailData.value.orders) || []);
const planDetailTitle = computed(() =>
  planDetailData.value && planDetailData.value.plan_no
    ? `调度方案详情 · ${planDetailData.value.plan_no}`
    : '调度方案详情'
);

async function loadPlans() {
  plansLoading.value = true;
  try {
    const range = planQuery.value.range || [];
    const data = await dispatchApi.plans(
      pruneParams({
        page: planPager.value.page,
        page_size: planPager.value.page_size,
        start_date: range[0] || null,
        end_date: range[1] || null,
        status: planQuery.value.status,
      })
    );
    plans.value = data.items || [];
    planPager.value.total = data.total || 0;
    plansLoaded.value = true;
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    plansLoading.value = false;
  }
}

function searchPlans() {
  planPager.value.page = 1;
  loadPlans();
}

function resetPlanQuery() {
  planQuery.value = { range: recentRange(30), status: null };
  planPager.value.page = 1;
  loadPlans();
}

async function openPlanDetail(row) {
  planDetailVisible.value = true;
  planDetailLoading.value = true;
  planDetailData.value = null;
  try {
    planDetailData.value = await dispatchApi.planDetail(row.id);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    planDetailLoading.value = false;
  }
}

async function changePlanStatus(row, status) {
  if (Number(status) === Number(row.status)) return;
  try {
    await dispatchApi.updatePlanStatus(row.id, status);
    ElMessage.success(`方案 ${row.plan_no} 状态已更新为「${planStatusText(status)}」`);
    await loadPlans();
    loadPlanOptions();
    loadEffectPlans();
    if (statLoaded.value) loadStatistics();
  } catch (error) {
    /* 拦截器已提示 */
  }
}

async function confirmRemovePlan(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除调度方案「${row.plan_no}」及其全部调度指令吗？该操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }
  try {
    await dispatchApi.removePlan(row.id);
    ElMessage.success('调度方案已删除');
    await loadPlans();
    loadPlanOptions();
  } catch (error) {
    /* 拦截器已提示 */
  }
}

/* ------------------------------------------ Tab4 调度单执行与效果评估 */
const planOptions = ref([]);
const effectPlans = ref([]);
const orderQuery = ref({ plan_id: null, status: null });
const orders = ref([]);
const ordersLoading = ref(false);
const ordersLoaded = ref(false);
const orderPager = ref({ page: 1, page_size: 10, total: 0 });

const statistics = ref({ by_status: [], by_strategy: [] });
const statLoading = ref(false);
const statLoaded = ref(false);

const effectPlanId = ref(null);
const effectLoading = ref(false);
const effectData = ref(null);
const effectDetail = computed(() => (effectData.value && effectData.value.detail) || []);

const feedbackVisible = ref(false);
const feedbackLoading = ref(false);
const feedbackRow = ref({});
const feedbackForm = ref({ status: 2, feedback: '' });

const strategyPie = computed(() =>
  ((statistics.value && statistics.value.by_strategy) || []).map((item) => ({
    name: strategyText(item.strategy),
    value: Number(item.plan_count || 0),
  }))
);
const statusPie = computed(() =>
  ((statistics.value && statistics.value.by_status) || []).map((item) => ({
    name: item.status_text || dispatchStatusText(item.status),
    value: Number(item.count || 0),
  }))
);

function pieOption(list) {
  return {
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c}（{d}%）' },
    legend: {
      orient: 'vertical',
      right: 0,
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#6b7280', fontSize: 11 },
    },
    color: PIE_COLORS,
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['38%', '52%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        labelLine: { show: false },
        data: list,
      },
    ],
  };
}

const strategyPieOption = computed(() => pieOption(strategyPie.value));
const statusPieOption = computed(() => pieOption(statusPie.value));

const effectOption = computed(() => {
  const detail = effectDetail.value;
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['预期净收益', '实际增收'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: detail.map((item) => item.dispatch_no),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7280',
        fontSize: 10,
        interval: 0,
        rotate: detail.length > 5 ? 30 : 0,
      },
    },
    yAxis: {
      type: 'value',
      name: '金额(元)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '预期净收益',
        type: 'bar',
        barMaxWidth: 26,
        data: detail.map((item) => item.expected_gain),
        itemStyle: { color: 'rgba(43,109,229,0.75)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '实际增收',
        type: 'bar',
        barMaxWidth: 26,
        data: detail.map((item) => item.actual_gain),
        itemStyle: {
          color: (params) => (Number(params.value) >= 0 ? 'rgba(16,185,129,0.85)' : '#ef4444'),
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  };
});

async function loadPlanOptions() {
  try {
    const data = await dispatchApi.plans(pruneParams({ page: 1, page_size: 100 }));
    planOptions.value = data.items || [];
  } catch (error) {
    /* 拦截器已提示 */
  }
}

async function loadEffectPlans() {
  try {
    const data = await dispatchApi.plans(pruneParams({ page: 1, page_size: 50, status: 3 }));
    effectPlans.value = data.items || [];
  } catch (error) {
    /* 拦截器已提示 */
  }
}

async function loadOrders() {
  ordersLoading.value = true;
  try {
    const data = await dispatchApi.orders(
      pruneParams({
        page: orderPager.value.page,
        page_size: orderPager.value.page_size,
        plan_id: orderQuery.value.plan_id,
        status: orderQuery.value.status,
      })
    );
    orders.value = data.items || [];
    orderPager.value.total = data.total || 0;
    ordersLoaded.value = true;
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    ordersLoading.value = false;
  }
}

function searchOrders() {
  orderPager.value.page = 1;
  loadOrders();
}

async function loadStatistics() {
  statLoading.value = true;
  try {
    statistics.value = await dispatchApi.statistics({ days: 30 });
    statLoaded.value = true;
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    statLoading.value = false;
  }
}

function openFeedback(row) {
  feedbackRow.value = row || {};
  feedbackForm.value = {
    status: 2,
    feedback: (row && row.feedback) || '',
  };
  feedbackVisible.value = true;
}

async function submitFeedback() {
  if (!feedbackRow.value.id) {
    ElMessage.warning('该调度指令尚未入库，无法提交反馈');
    return;
  }
  feedbackLoading.value = true;
  try {
    await dispatchApi.feedback(feedbackRow.value.id, {
      status: feedbackForm.value.status,
      feedback: feedbackForm.value.feedback,
    });
    ElMessage.success('调度执行反馈已提交');
    feedbackVisible.value = false;
    await loadOrders();
    loadPlans();
    loadEffectPlans();
    if (statLoaded.value) loadStatistics();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    feedbackLoading.value = false;
  }
}

async function loadEffect() {
  if (!effectPlanId.value) {
    ElMessage.warning('请先选择一个已完成的调度方案');
    return;
  }
  effectLoading.value = true;
  try {
    effectData.value = await dispatchApi.effect(effectPlanId.value);
    ElMessage.success(`效果评估完成：实际净收益 ${money(effectData.value.actual_gain)} 元`);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    effectLoading.value = false;
  }
}

/* ------------------------------------------------------------ 生命周期 */
async function refreshCurrent() {
  refreshing.value = true;
  try {
    if (activeTab.value === 'plans') {
      await loadPlans();
    } else if (activeTab.value === 'execute') {
      await Promise.all([loadOrders(), loadStatistics(), loadPlanOptions(), loadEffectPlans()]);
    } else {
      await loadStatus();
    }
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    refreshing.value = false;
  }
}

onMounted(async () => {
  booting.value = true;
  try {
    await Promise.all([loadStatus(), loadPlanOptions(), loadEffectPlans()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    booting.value = false;
  }
});

watch(activeTab, (tab) => {
  if (tab === 'plans' && !plansLoaded.value) loadPlans();
  if (tab === 'execute') {
    if (!ordersLoaded.value) loadOrders();
    if (!statLoaded.value) loadStatistics();
  }
});
</script>

<style scoped>
.filter-label {
  font-size: 13px;
  color: var(--app-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.hint {
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.mb-8 {
  margin-bottom: 8px;
}
.ml-4 {
  margin-left: 4px;
}
.warn-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
  margin-bottom: 8px;
}
.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.exp-block {
  margin-bottom: 6px;
}
.exp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.exp-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--app-text);
}
.exp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
