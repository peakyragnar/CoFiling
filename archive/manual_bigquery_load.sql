-- Manual BigQuery data load for SEC data
-- Run this in BigQuery console

-- Insert facts
INSERT INTO `sec-ai-466316.sec_data.facts` (cik, entity_name, concept, value, unit, period_end, source)
VALUES
  ('1318605', 'Tesla, Inc.', 'AccountsAndNotesReceivableNet', 402000000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccountsPayableCurrent', 28951000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccountsReceivableNetCurrent', 6710000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccretionAmortizationOfDiscountsAndPremiumsInvestments', 112000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccrualForEnvironmentalLossContingencies', 5300000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccrualForEnvironmentalLossContingenciesPayments', 3100000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccruedEnvironmentalLossContingenciesCurrent', 2132000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccruedEnvironmentalLossContingenciesNoncurrent', 5300000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccruedLiabilitiesCurrent', 20945000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment', 21993000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AccumulatedOtherComprehensiveIncomeLossNetOfTax', -24000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdditionalPaidInCapital', 621935000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdditionalPaidInCapitalCommonStock', 1806617000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsNoncashItemsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities', 233000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsToAdditionalPaidInCapitalEquityComponentOfConvertibleDebt', 82842000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsToAdditionalPaidInCapitalOther', 4120000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationRequisiteServicePeriodRecognitionValue', 1434000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsToAdditionalPaidInCapitalTaxEffectFromShareBasedCompensation', 74000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdjustmentsToAdditionalPaidInCapitalWarrantIssued', 120318000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AdvertisingRevenueCost', 48900000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AllocatedShareBasedCompensationExpense', 1434000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AmortizationOfDebtDiscountPremium', 2686000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AmortizationOfFinancingCosts', 1207000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AmortizationOfFinancingCostsAndDiscounts', 78054000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AmortizationOfIntangibleAssets', 40000000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AreaOfRealEstateProperty', 350000, 'sqft', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AssetBackedSecuritiesAtCarryingValue', 50000000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'AssetRetirementObligationsNoncurrent', 2115000, 'USD', '2025-03-31', 'xbrl_instance'),
  ('1318605', 'Tesla, Inc.', 'Assets', 386082000, 'USD', '2025-03-31', 'xbrl_instance');

