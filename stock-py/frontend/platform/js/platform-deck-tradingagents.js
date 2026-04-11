function createPlatformDeckTradingAgentsState(constants = {}) {
    return {
        tradingAgentsDraft: constants.createTradingAgentsDraft
            ? constants.createTradingAgentsDraft()
            : {
                ticker: 'AAPL',
                analysisDate: new Date().toISOString().slice(0, 10),
                triggerType: 'manual',
                source: 'platform',
                runId: '',
                selectedAnalysts: ''
            },
        tradingAgentsIncludeFullPayload: false,
        tradingAgentsStatusMessage: '等待提交 TradingAgents 分析任务',
        tradingAgentsSubmitting: false,
        tradingAgentsPolling: false,
        tradingAgentsRuns: [],
        tradingAgentsActiveRequestId: '',
        tradingAgentsPollInFlight: {},
        tradingAgentsPollHandle: null,
    };
}

function createPlatformDeckTradingAgentsModule(utils = {}) {
    return {
        normalizeTradingAgentsSlug: utils.normalizeTradingAgentsSlug,

        normalizeTradingAgentsAnalysisDate: utils.normalizeTradingAgentsAnalysisDate,

        buildTradingAgentsRequestId: utils.buildTradingAgentsRequestId,

        normalizeTradingAgentsStatus: utils.normalizeTradingAgentsStatus,

        tradingAgentsStatusLabel: utils.tradingAgentsStatusLabel,

        tradingAgentsStatusClass: utils.tradingAgentsStatusClass,

        tradingAgentsActionLabel: utils.tradingAgentsActionLabel,

        isTradingAgentsTerminal: utils.isTradingAgentsTerminal,

        pickFirstText: utils.pickFirstText,

        extractTradingAgentsUris: utils.extractTradingAgentsUris,

        pendingTradingAgentsRunsCount() {
            return this.tradingAgentsRuns.filter((item) => !this.isTradingAgentsTerminal(item.status)).length;
        },

        persistTradingAgentsOptions() {
            localStorage.setItem(
                this.storageKeys.taIncludeFullPayload,
                this.tradingAgentsIncludeFullPayload ? 'true' : 'false'
            );
        },

        consumeTradingAgentsAnalyses(payload) {
            const rows = Array.isArray(payload && payload.data) ? payload.data : [];
            rows.forEach((item) => {
                const requestId = String(item.request_id || '').trim();
                if (!requestId) {
                    return;
                }
                this.upsertTradingAgentsRun({
                    request_id: requestId,
                    ticker: String(item.ticker || '').toUpperCase(),
                    job_id: String(item.job_id || ''),
                    trigger_type: String(item.trigger_type || 'manual').toLowerCase(),
                    analysis_date: item.analysis_date || '',
                    status: this.normalizeTradingAgentsStatus(item.tradingagents_status),
                    final_action: String(item.final_action || ''),
                    decision_summary: String(item.decision_summary || ''),
                    poll_count: Number(item.poll_count || 0),
                    submitted_at: item.submitted_at || item.created_at || '',
                    completed_at: item.completed_at || '',
                    updated_at: item.completed_at || item.submitted_at || item.created_at || new Date().toISOString(),
                    webhook_received: Boolean(item.webhook_received)
                });
            });

            if (!this.tradingAgentsActiveRequestId && this.tradingAgentsRuns.length) {
                this.tradingAgentsActiveRequestId = this.tradingAgentsRuns[0].request_id;
            }
        },

        tradingAgentsRunSummary(run) {
            if (!run) {
                return '--';
            }
            if (run.decision_summary) {
                return run.decision_summary;
            }
            if (this.isTradingAgentsTerminal(run.status)) {
                return '任务已终态完成，但未返回摘要文本。';
            }
            return '等待终态结果，webhook 与轮询会共同收敛状态。';
        },

        upsertTradingAgentsRun(patch) {
            const requestId = String(patch && patch.request_id ? patch.request_id : '').trim();
            if (!requestId) {
                return;
            }
            const index = this.tradingAgentsRuns.findIndex((item) => item.request_id === requestId);
            const previous = index >= 0 ? this.tradingAgentsRuns[index] : null;
            const next = {
                request_id: requestId,
                ticker: '',
                job_id: '',
                trigger_type: 'manual',
                analysis_date: '',
                status: 'pending',
                final_action: '',
                decision_summary: '',
                report_uri: '',
                result_uri: '',
                poll_count: 0,
                submitted_at: '',
                completed_at: '',
                updated_at: new Date().toISOString(),
                webhook_received: false,
                http_status: null,
                ...(previous || {}),
                ...(patch || {})
            };

            if (index >= 0) {
                this.tradingAgentsRuns = [
                    ...this.tradingAgentsRuns.slice(0, index),
                    next,
                    ...this.tradingAgentsRuns.slice(index + 1)
                ];
            } else {
                this.tradingAgentsRuns = [...this.tradingAgentsRuns, next];
            }
            this.sortTradingAgentsRuns();
        },

        sortTradingAgentsRuns() {
            const rowScore = (row) => {
                const candidates = [row.updated_at, row.completed_at, row.submitted_at, row.analysis_date];
                for (const candidate of candidates) {
                    if (!candidate) {
                        continue;
                    }
                    const parsed = new Date(candidate);
                    if (!Number.isNaN(parsed.getTime())) {
                        return parsed.getTime();
                    }
                }
                return 0;
            };

            this.tradingAgentsRuns = [...this.tradingAgentsRuns]
                .sort((left, right) => rowScore(right) - rowScore(left))
                .slice(0, 40);
        },

        async refreshTradingAgentsAnalyses(options = {}) {
            try {
                const payload = await this.apiRequest('/v1/admin/tradingagents/analyses?limit=16');
                this.consumeTradingAgentsAnalyses(payload);
                if (!options.silent) {
                    this.tradingAgentsStatusMessage = `已同步分析列表，共 ${this.formatInt(this.tradingAgentsRuns.length)} 条。`;
                    this.log('ok', `TradingAgents 分析列表已同步 ${this.tradingAgentsRuns.length} 条。`);
                }
            } catch (error) {
                if (!options.silent) {
                    this.tradingAgentsStatusMessage = `分析列表同步失败: ${error.message || '未知错误'}`;
                }
                this.log('warn', `TradingAgents 分析列表同步失败: ${error.message || '未知错误'}`);
            }
        },

        async submitTradingAgentsAnalysis() {
            if (this.tradingAgentsSubmitting) {
                return;
            }

            const ticker = String(this.tradingAgentsDraft.ticker || '').trim().toUpperCase();
            if (!ticker) {
                this.tradingAgentsStatusMessage = '请先输入 ticker。';
                return;
            }

            const analysisDate = this.normalizeTradingAgentsAnalysisDate(this.tradingAgentsDraft.analysisDate);
            if (!analysisDate) {
                this.tradingAgentsStatusMessage = '请先选择有效 analysis date。';
                return;
            }

            const triggerType = String(this.tradingAgentsDraft.triggerType || 'manual').trim().toLowerCase();
            const triggerTypeAllowed = ['manual', 'scanner', 'position_review', 'scheduled'];
            if (!triggerTypeAllowed.includes(triggerType)) {
                this.tradingAgentsStatusMessage = 'trigger_type 不合法。';
                return;
            }

            const source = this.normalizeTradingAgentsSlug(this.tradingAgentsDraft.source, 20, 'platform');
            const runIdRaw = String(this.tradingAgentsDraft.runId || '').trim() || `ui-${Date.now().toString(36)}`;
            const runId = this.normalizeTradingAgentsSlug(runIdRaw, 24, 'ui');
            const requestId = this.buildTradingAgentsRequestId({
                ticker,
                analysisDate,
                triggerType,
                source,
                runId
            });

            const payload = {
                request_id: requestId,
                ticker,
                analysis_date: `${analysisDate}T00:00:00Z`,
                trigger_type: triggerType,
                trigger_context: {
                    source,
                    run_id: runId,
                    surface: 'platform'
                }
            };

            const analysts = this.parseCsvStrings(this.tradingAgentsDraft.selectedAnalysts)
                .map((item) => item.toLowerCase());
            if (analysts.length) {
                payload.selected_analysts = analysts;
            }

            this.tradingAgentsSubmitting = true;
            this.tradingAgentsStatusMessage = `提交中: ${requestId}`;

            try {
                const result = await this.publicApiRequest('/v1/internal/tradingagents/submit', {
                    method: 'POST',
                    body: payload,
                    includeAuth: true
                });

                const nextStatus = this.normalizeTradingAgentsStatus(result && result.status);
                this.upsertTradingAgentsRun({
                    request_id: requestId,
                    ticker,
                    job_id: String((result && result.job_id) || ''),
                    trigger_type: triggerType,
                    analysis_date: `${analysisDate}T00:00:00Z`,
                    status: nextStatus,
                    decision_summary: String((result && result.message) || ''),
                    poll_count: 0,
                    submitted_at: new Date().toISOString(),
                    updated_at: new Date().toISOString()
                });
                this.tradingAgentsActiveRequestId = requestId;
                this.tradingAgentsStatusMessage = `提交成功: ${requestId}`;
                this.log('ok', `TradingAgents 提交成功 ticker=${ticker} request_id=${requestId} status=${nextStatus}`);

                await this.pollTradingAgentsResult(requestId, { silent: true });
                await this.refreshTradingAgentsAnalyses({ silent: true });
            } catch (error) {
                this.tradingAgentsStatusMessage = `提交失败: ${error.message || '未知错误'}`;
                this.log('warn', `TradingAgents 提交失败 ticker=${ticker}: ${error.message || '未知错误'}`);
            } finally {
                this.tradingAgentsSubmitting = false;
            }
        },

        async pollTradingAgentsResult(requestId, options = {}) {
            const targetRequestId = String(requestId || this.tradingAgentsActiveRequestId || '').trim();
            if (!targetRequestId) {
                if (!options.silent) {
                    this.tradingAgentsStatusMessage = '缺少 request_id，无法轮询。';
                }
                return;
            }

            if (this.tradingAgentsPollInFlight[targetRequestId]) {
                return;
            }
            this.tradingAgentsPollInFlight = {
                ...this.tradingAgentsPollInFlight,
                [targetRequestId]: true
            };

            try {
                const includeFullResult = this.tradingAgentsIncludeFullPayload ? 'true' : 'false';
                const encodedRequestId = encodeURIComponent(targetRequestId);
                const { status, payload } = await this.publicApiRequestWithStatus(
                    `/v1/internal/tradingagents/stock-result/${encodedRequestId}?include_full_result_payload=${includeFullResult}`,
                    {
                        includeAuth: true,
                        expectedStatuses: [202, 404, 409]
                    }
                );

                const safePayload = payload && typeof payload === 'object' ? payload : {};
                const normalizedStatus = status === 404
                    ? 'pending'
                    : this.normalizeTradingAgentsStatus(
                        safePayload.tradingagents_status || safePayload.status,
                        status
                    );
                const extractedUris = this.extractTradingAgentsUris(safePayload);
                const finalAction = this.pickFirstText([
                    safePayload.final_action,
                    safePayload.result_payload && safePayload.result_payload.final_action,
                    safePayload.result && safePayload.result.final_action
                ]);
                const decisionSummary = this.pickFirstText([
                    safePayload.decision_summary,
                    safePayload.error_message,
                    safePayload.error,
                    safePayload.detail,
                    status === 404 ? '未找到结果，可能仍在排队或请求已过期。' : ''
                ]);

                const existing = this.tradingAgentsRuns.find((item) => item.request_id === targetRequestId);
                const nextPollCount = Number((existing && existing.poll_count) || 0) + 1;
                const patch = {
                    request_id: targetRequestId,
                    job_id: this.pickFirstText([safePayload.job_id]),
                    status: normalizedStatus,
                    final_action: finalAction,
                    decision_summary: decisionSummary,
                    report_uri: extractedUris.report_uri,
                    result_uri: extractedUris.result_uri,
                    http_status: status,
                    poll_count: nextPollCount,
                    updated_at: new Date().toISOString()
                };
                if (this.isTradingAgentsTerminal(normalizedStatus)) {
                    patch.completed_at = new Date().toISOString();
                }
                this.upsertTradingAgentsRun(patch);

                if (!options.silent) {
                    this.tradingAgentsStatusMessage = `${targetRequestId} 轮询状态: ${this.tradingAgentsStatusLabel(normalizedStatus)} (HTTP ${status})`;
                }
                if (this.isTradingAgentsTerminal(normalizedStatus)) {
                    const level = normalizedStatus === 'completed' ? 'ok' : 'warn';
                    this.log(level, `TradingAgents 任务 ${targetRequestId} 已终态: ${this.tradingAgentsStatusLabel(normalizedStatus)}`);
                }
            } catch (error) {
                if (!options.silent) {
                    this.tradingAgentsStatusMessage = `${targetRequestId} 轮询失败: ${error.message || '未知错误'}`;
                }
                this.log('warn', `TradingAgents 轮询失败 request_id=${targetRequestId}: ${error.message || '未知错误'}`);
            } finally {
                const nextInFlight = { ...this.tradingAgentsPollInFlight };
                delete nextInFlight[targetRequestId];
                this.tradingAgentsPollInFlight = nextInFlight;
            }
        },

        async pollPendingTradingAgentsRuns(force = false) {
            if (this.tradingAgentsPolling && !force) {
                return;
            }

            const pendingRuns = this.tradingAgentsRuns
                .filter((item) => !this.isTradingAgentsTerminal(item.status))
                .slice(0, 4);
            if (!pendingRuns.length) {
                return;
            }

            this.tradingAgentsPolling = true;
            try {
                for (const item of pendingRuns) {
                    await this.pollTradingAgentsResult(item.request_id, { silent: true });
                }
            } finally {
                this.tradingAgentsPolling = false;
            }
        },
    };
}

window.PlatformDeckTradingAgents = {
    createState: createPlatformDeckTradingAgentsState,
    createModule: createPlatformDeckTradingAgentsModule,
};
