/**
 * SEC Financial Model - Google Sheets Automation
 * Main Apps Script code for connecting to BigQuery and building financial models
 */

// Configuration
const PROJECT_ID = 'sec-ai-466316';
const DATASET_ID = 'sec_data';

/**
 * Custom menu creation
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('SEC Analysis')
    .addItem('Refresh Data', 'refreshAllData')
    .addItem('Build Financial Model', 'buildFinancialModel')
    .addItem('Update Segment Analysis', 'updateSegmentAnalysis')
    .addSeparator()
    .addItem('Configure Companies', 'showCompanyConfig')
    .addItem('Generate AI Summary', 'generateAISummary')
    .addToUi();
}

/**
 * Refresh all BigQuery data connections
 */
function refreshAllData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  
  ui.alert('Refreshing data...', 'Updating all BigQuery connections', ui.ButtonSet.OK);
  
  try {
    // Get all data source tables
    const dataSources = sheet.getDataSourceTables();
    
    dataSources.forEach(table => {
      console.log(`Refreshing ${table.getDataSource().getSpec().getType()}`);
      table.refreshData();
    });
    
    // Update last refresh timestamp
    const configSheet = sheet.getSheetByName('Config') || sheet.insertSheet('Config');
    configSheet.getRange('A1').setValue('Last Refresh:');
    configSheet.getRange('B1').setValue(new Date());
    
    ui.alert('Success', 'All data has been refreshed', ui.ButtonSet.OK);
    
  } catch (error) {
    ui.alert('Error', `Failed to refresh data: ${error.toString()}`, ui.ButtonSet.OK);
  }
}

/**
 * Build financial model from BigQuery data
 */
function buildFinancialModel() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const modelSheet = sheet.getSheetByName('Financial Model') || sheet.insertSheet('Financial Model');
  
  // Clear existing content
  modelSheet.clear();
  
  // Set headers
  const headers = [
    ['Financial Model - SEC Data Analysis'],
    [''],
    ['Company', 'Period', 'Revenue', 'Growth %', 'Operating Income', 'Margin %', 'Net Income', 'EPS']
  ];
  
  modelSheet.getRange(1, 1, headers.length, headers[0].length).setValues(headers);
  
  // Style headers
  modelSheet.getRange('A1:H1').merge()
    .setFontSize(16)
    .setFontWeight('bold')
    .setHorizontalAlignment('center');
  
  modelSheet.getRange('A3:H3')
    .setFontWeight('bold')
    .setBackground('#4285F4')
    .setFontColor('white');
  
  // Fetch data from BigQuery
  const query = `
    SELECT 
      f.entity_name,
      f.period_end,
      MAX(CASE WHEN f.concept = 'Revenues' THEN f.value END) as revenue,
      MAX(CASE WHEN f.concept = 'OperatingIncomeLoss' THEN f.value END) as operating_income,
      MAX(CASE WHEN f.concept = 'NetIncomeLoss' THEN f.value END) as net_income,
      MAX(CASE WHEN f.concept = 'EarningsPerShareBasic' THEN f.value END) as eps
    FROM \`${PROJECT_ID}.${DATASET_ID}.facts\` f
    WHERE f.concept IN ('Revenues', 'OperatingIncomeLoss', 'NetIncomeLoss', 'EarningsPerShareBasic')
      AND f.period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
    GROUP BY f.entity_name, f.period_end
    ORDER BY f.entity_name, f.period_end DESC
  `;
  
  try {
    const results = runBigQuery(query);
    let row = 4;
    let previousRevenue = {};
    
    results.forEach(record => {
      const company = record.entity_name;
      const revenue = parseFloat(record.revenue || 0);
      const operatingIncome = parseFloat(record.operating_income || 0);
      const netIncome = parseFloat(record.net_income || 0);
      const eps = parseFloat(record.eps || 0);
      
      // Calculate growth
      let growth = '';
      if (previousRevenue[company]) {
        growth = ((revenue - previousRevenue[company]) / previousRevenue[company] * 100).toFixed(1) + '%';
      }
      previousRevenue[company] = revenue;
      
      // Calculate margin
      const margin = revenue > 0 ? (operatingIncome / revenue * 100).toFixed(1) + '%' : '';
      
      // Write row
      modelSheet.getRange(row, 1, 1, 8).setValues([[
        company,
        record.period_end,
        revenue,
        growth,
        operatingIncome,
        margin,
        netIncome,
        eps
      ]]);
      
      row++;
    });
    
    // Format numbers
    modelSheet.getRange(4, 3, row - 4, 1).setNumberFormat('$#,##0');  // Revenue
    modelSheet.getRange(4, 5, row - 4, 1).setNumberFormat('$#,##0');  // Operating Income
    modelSheet.getRange(4, 7, row - 4, 1).setNumberFormat('$#,##0');  // Net Income
    modelSheet.getRange(4, 8, row - 4, 1).setNumberFormat('$0.00');   // EPS
    
    // Auto-resize columns
    modelSheet.autoResizeColumns(1, 8);
    
    // Add charts
    addFinancialCharts(modelSheet, row - 1);
    
  } catch (error) {
    SpreadsheetApp.getUi().alert('Error', `Failed to build model: ${error.toString()}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Update segment analysis with pivot tables
 */
function updateSegmentAnalysis() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const segmentSheet = sheet.getSheetByName('Segment Analysis') || sheet.insertSheet('Segment Analysis');
  
  segmentSheet.clear();
  
  // Query segment data
  const query = `
    SELECT 
      s.dimension_axis,
      s.dimension_member,
      s.concept,
      s.period_end,
      s.value,
      s.cik
    FROM \`${PROJECT_ID}.${DATASET_ID}.segments\` s
    WHERE s.concept IN ('Revenues', 'CostOfRevenue')
      AND s.period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
    ORDER BY s.dimension_axis, s.dimension_member, s.period_end DESC
  `;
  
  try {
    const results = runBigQuery(query);
    
    // Create headers
    segmentSheet.getRange('A1').setValue('Segment Analysis');
    segmentSheet.getRange('A1').setFontSize(16).setFontWeight('bold');
    
    // Write data
    const headers = ['Dimension', 'Member', 'Concept', 'Period', 'Value'];
    segmentSheet.getRange('A3:E3').setValues([headers]);
    segmentSheet.getRange('A3:E3').setFontWeight('bold').setBackground('#34A853');
    
    let row = 4;
    results.forEach(record => {
      segmentSheet.getRange(row, 1, 1, 5).setValues([[
        record.dimension_axis,
        record.dimension_member,
        record.concept,
        record.period_end,
        parseFloat(record.value || 0)
      ]]);
      row++;
    });
    
    // Format values
    segmentSheet.getRange(4, 5, row - 4, 1).setNumberFormat('$#,##0');
    
    // Create pivot table
    createSegmentPivotTable(segmentSheet, row);
    
  } catch (error) {
    SpreadsheetApp.getUi().alert('Error', `Failed to update segments: ${error.toString()}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Run BigQuery query
 */
function runBigQuery(query) {
  const request = BigQuery.newQueryRequest();
  request.query = query;
  request.useLegacySql = false;
  
  const response = BigQuery.Jobs.query(request, PROJECT_ID);
  
  if (response.jobComplete) {
    return response.rows.map(row => {
      const record = {};
      row.f.forEach((field, index) => {
        const fieldName = response.schema.fields[index].name;
        record[fieldName] = field.v;
      });
      return record;
    });
  } else {
    throw new Error('Query timeout');
  }
}

/**
 * Add financial charts to the model
 */
function addFinancialCharts(sheet, lastRow) {
  // Revenue trend chart
  const revenueChart = sheet.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(sheet.getRange(3, 1, lastRow - 2, 3))  // Company, Period, Revenue
    .setPosition(5, 10, 0, 0)
    .setOption('title', 'Revenue Trend')
    .setOption('width', 600)
    .setOption('height', 400)
    .build();
  
  sheet.insertChart(revenueChart);
  
  // Margin analysis chart
  const marginChart = sheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(sheet.getRange(3, 1, lastRow - 2, 1))  // Company
    .addRange(sheet.getRange(3, 6, lastRow - 2, 1))  // Margin %
    .setPosition(25, 10, 0, 0)
    .setOption('title', 'Operating Margin by Company')
    .setOption('width', 600)
    .setOption('height', 400)
    .build();
  
  sheet.insertChart(marginChart);
}

/**
 * Create segment pivot table
 */
function createSegmentPivotTable(sheet, dataLastRow) {
  const sourceRange = sheet.getRange(3, 1, dataLastRow - 3, 5);
  
  const pivotTable = sheet.newPivotTable()
    .setDataSourceRange(sourceRange)
    .addRowGroup(1)  // Dimension
    .addRowGroup(2)  // Member
    .addColumnGroup(4)  // Period
    .addValue(5, SpreadsheetApp.PivotTableSummarizeFunction.SUM)  // Value
    .setValuesDisplayOrientation(SpreadsheetApp.PivotValueDisplayType.HORIZONTAL)
    .build();
  
  sheet.insertPivotTable(pivotTable, sheet.getRange('H3'));
}

/**
 * Show company configuration dialog
 */
function showCompanyConfig() {
  const html = HtmlService.createHtmlOutputFromFile('CompanyConfig')
    .setWidth(400)
    .setHeight(300);
  
  SpreadsheetApp.getUi().showModalDialog(html, 'Configure Companies');
}

/**
 * Save company configuration
 */
function saveCompanyConfig(companies) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const configSheet = sheet.getSheetByName('Config') || sheet.insertSheet('Config');
  
  // Clear existing config
  const lastRow = configSheet.getLastRow();
  if (lastRow > 3) {
    configSheet.getRange(4, 1, lastRow - 3, 2).clear();
  }
  
  // Write headers
  configSheet.getRange('A3:B3').setValues([['CIK', 'Company Name']]);
  configSheet.getRange('A3:B3').setFontWeight('bold');
  
  // Write companies
  companies.forEach((company, index) => {
    configSheet.getRange(4 + index, 1, 1, 2).setValues([[company.cik, company.name]]);
  });
  
  return true;
}

/**
 * Get configured companies
 */
function getConfiguredCompanies() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const configSheet = sheet.getSheetByName('Config');
  
  if (!configSheet) {
    // Return default companies
    return [
      {cik: '0001318605', name: 'Tesla'},
      {cik: '0000320193', name: 'Apple'},
      {cik: '0001652044', name: 'Alphabet'}
    ];
  }
  
  const lastRow = configSheet.getLastRow();
  if (lastRow < 4) return [];
  
  const data = configSheet.getRange(4, 1, lastRow - 3, 2).getValues();
  return data.map(row => ({cik: row[0], name: row[1]})).filter(c => c.cik);
}