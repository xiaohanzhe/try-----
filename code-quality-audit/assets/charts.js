// 图表初始化
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var critical = style.getPropertyValue('--critical').trim();
  var danger = style.getPropertyValue('--danger').trim();
  var warning = style.getPropertyValue('--warning').trim();
  var success = style.getPropertyValue('--success').trim();

  // --- Chart 1: 各模块问题数量分布 ---
  var chartModules = echarts.init(document.getElementById('chart-modules'), null, { renderer: 'svg' });
  chartModules.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true
    },
    legend: {
      data: ['严重', '高危', '中危', '低危'],
      textStyle: { color: muted },
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['desktop_interaction', 'sprite_loader', 'api_client', 'pet_ai', 'autonomous_agent', 'emotion_system', 'config_manager', 'dialogue_system', 'sound_manager', 'social_growth', '其他模块'],
      axisLabel: {
        color: muted,
        rotate: 30,
        fontSize: 11
      },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [
      {
        name: '严重',
        type: 'bar',
        stack: 'total',
        data: [5, 1, 0, 0, 1, 2, 1, 0, 0, 1, 1],
        itemStyle: { color: critical }
      },
      {
        name: '高危',
        type: 'bar',
        stack: 'total',
        data: [9, 4, 3, 3, 2, 3, 2, 3, 2, 2, 5],
        itemStyle: { color: danger }
      },
      {
        name: '中危',
        type: 'bar',
        stack: 'total',
        data: [12, 10, 8, 8, 7, 6, 7, 6, 6, 5, 10],
        itemStyle: { color: warning }
      },
      {
        name: '低危',
        type: 'bar',
        stack: 'total',
        data: [6, 6, 6, 5, 6, 4, 4, 5, 6, 4, 6],
        itemStyle: { color: success }
      }
    ]
  });

  // --- Chart 2: 问题类型分类统计 ---
  var chartTypes = echarts.init(document.getElementById('chart-types'), null, { renderer: 'svg' });
  chartTypes.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: muted }
    },
    series: [
      {
        name: '问题类型',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: bg2,
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: ink
          }
        },
        labelLine: { show: false },
        data: [
          { value: 35, name: '隐藏bug', itemStyle: { color: critical } },
          { value: 28, name: '边界条件', itemStyle: { color: danger } },
          { value: 25, name: '重复编码', itemStyle: { color: warning } },
          { value: 38, name: '拓展坑点', itemStyle: { color: accent } },
          { value: 31, name: '异常处理', itemStyle: { color: accent2 } }
        ]
      }
    ]
  });

  window.addEventListener('resize', function() {
    chartModules.resize();
    chartTypes.resize();
  });
})();
