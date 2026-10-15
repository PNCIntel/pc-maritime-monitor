"""Offline publication-context regressions: no live database or AI required."""
import unittest
from pc_publication_context import build_context


class PublicationContextTests(unittest.TestCase):
    def test_df_peak_identity_and_sanctions_stay_distinct(self):
        context=build_context(
            {"title":"French Navy boards DF Peak","start_date":"2026-10-12"},
            vessel={"name":"DF Peak","imo":"9341067","metadata":{"former_names":["Kaliningrad","NS Captain"]}},
            company_roles=[({"relationship_type":"historical_manager","valid_to":"2024-06-01"},
                            {"name":"Historical operator"})],
            designations=[({"review_status":"reviewed","is_direct_designation":True},
                           {"primary_name":"DF Peak","source_list":"Example authority","designation_date":"2024-01-01"})],
            pgsa_queue=[{"authority_code":"PGSA","subject_identifier":"9341067","research_status":"pending"}])
        self.assertEqual(context["vessel_profile"]["imo"],"9341067")
        self.assertEqual(len(context["published_sanctions"]),1)
        self.assertEqual(len(context["non_designation_research"]),1)
        self.assertIn("not a legal sanctions designation",context["non_designation_research"][0]["qualification"])
        self.assertEqual(context["company_history"][0]["relationship"]["valid_to"],"2024-06-01")

    def test_istanbul_connected_assets_do_not_imply_damage(self):
        context=build_context({"title":"Istanbul weather disruption"},
            assets=[{"name":"Istanbul Airport","mode":"airport","relationship":"diverted arrivals",
                     "impact_status":"recorded operational disruption"}],
            related=[({"relationship_type":"associated_weather_context"},
                      {"title":"Rail services extended","verification_status":"verified"})])
        self.assertEqual(context["infrastructure"][0]["impact_status"],"recorded operational disruption")
        self.assertIn("does not prove shared cause",context["related_developments"][0]["qualification"])

    def test_missing_links_are_not_clearance(self):
        context=build_context({"title":"Incident with missing context"})
        self.assertTrue(context["coverage_gaps"])
        self.assertIn("not a clearance finding"," ".join(context["coverage_gaps"]))


if __name__=="__main__":
    unittest.main()
