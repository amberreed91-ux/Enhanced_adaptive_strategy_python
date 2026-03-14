import requests
import sys
import json
from datetime import datetime, timedelta

class QuantLabAPITester:
    def __init__(self, base_url="https://backtester-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.created_resources = {
            'feeds': [],
            'features': [],
            'signals': [],
            'strategies': [],
            'backtests': []
        }

    def run_test(self, name, method, endpoint, expected_status, data=None, auth_required=True):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if auth_required and self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json().get('detail', 'No detail')
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text[:200]}")

            return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_auth_flow(self):
        """Test complete authentication flow"""
        print("\n🔐 TESTING AUTHENTICATION")
        
        # Test user registration
        test_user = f"testuser_{datetime.now().strftime('%H%M%S')}"
        test_email = f"{test_user}@testlab.com"
        test_password = "TestPass123!"
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "name": test_user,
                "email": test_email, 
                "password": test_password
            },
            auth_required=False
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            print(f"   Registered user: {test_email}")
        else:
            print("❌ Registration failed - stopping auth tests")
            return False
            
        # Test user login  
        success, response = self.run_test(
            "User Login",
            "POST", 
            "auth/login",
            200,
            data={"email": test_email, "password": test_password},
            auth_required=False
        )
        
        if not success:
            print("❌ Login failed")
            return False
            
        # Test get current user
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me", 
            200
        )
        
        return success

    def test_market_data_apis(self):
        """Test market data management APIs"""
        print("\n📊 TESTING MARKET DATA APIs")
        
        # Get assets
        success, assets = self.run_test(
            "Get Assets",
            "GET",
            "market-data/assets",
            200
        )
        if not success:
            return False
            
        # Get exchanges  
        success, exchanges = self.run_test(
            "Get Exchanges",
            "GET",
            "market-data/exchanges", 
            200
        )
        if not success:
            return False
            
        # Create market data feed
        success, feed_response = self.run_test(
            "Create Market Data Feed",
            "POST",
            "market-data/ingest",
            200,
            data={
                "asset": "BTC/USDT",
                "exchange": "Binance", 
                "timeframe": "1D",
                "data_type": "OHLC"
            }
        )
        
        if success and 'id' in feed_response:
            self.created_resources['feeds'].append(feed_response['id'])
            
        # Get feeds
        success, _ = self.run_test(
            "Get Market Feeds",
            "GET",
            "market-data/feeds",
            200
        )
        
        # Test order book
        success, _ = self.run_test(
            "Get Order Book",
            "GET", 
            "market-data/orderbook/BTC%2FUSDT",
            200
        )
        
        return success

    def test_feature_generation_apis(self):
        """Test feature generation APIs"""
        print("\n🧠 TESTING FEATURE GENERATION APIs")
        
        # Generate features
        success, features_response = self.run_test(
            "Generate Features",
            "POST",
            "features/generate",
            200,
            data=[
                {
                    "name": "Momentum_5_Test",
                    "category": "price",
                    "definition": {"type": "momentum", "lookback": 5}
                },
                {
                    "name": "Volume_Spike_Test", 
                    "category": "volume",
                    "definition": {"type": "volume_spike", "threshold": 2.0}
                }
            ]
        )
        
        if success and features_response:
            for feature in features_response:
                if 'id' in feature:
                    self.created_resources['features'].append(feature['id'])
        
        # Get features
        success, _ = self.run_test(
            "Get Features",
            "GET",
            "features/",
            200
        )
        
        return success

    def test_signals_apis(self):
        """Test alpha signals APIs"""
        print("\n⚡ TESTING SIGNALS APIs")
        
        if not self.created_resources['features']:
            print("⏭️  Skipping signals tests - no features created")
            return True
            
        # Create signal
        success, signal_response = self.run_test(
            "Create Alpha Signal", 
            "POST",
            "signals/",
            200,
            data={
                "name": "Test_Signal_1",
                "feature_id": self.created_resources['features'][0],
                "threshold_values": {"upper": 0.7, "lower": -0.7},
                "market": "crypto"
            }
        )
        
        if success and 'id' in signal_response:
            self.created_resources['signals'].append(signal_response['id'])
            
        # Get signals
        success, _ = self.run_test(
            "Get Signals",
            "GET", 
            "signals/",
            200
        )
        
        return success

    def test_strategies_apis(self):
        """Test strategy management APIs"""
        print("\n🎯 TESTING STRATEGY APIs")
        
        if not self.created_resources['signals']:
            print("⏭️  Skipping strategy tests - no signals created")
            return True
            
        # Create strategy
        success, strategy_response = self.run_test(
            "Create Strategy",
            "POST",
            "strategies/",
            200,
            data={
                "name": "Test_Strategy_1",
                "signal_ids": [self.created_resources['signals'][0]], 
                "entry_rules": {"condition": "signal_threshold", "value": 0.5},
                "exit_rules": {"target": 2.0, "stop": 1.0, "trailing_stop": 0.5},
                "position_sizing": "fixed",
                "risk_params": {
                    "max_loss_per_trade": 1.0,
                    "max_daily_loss": 3.0, 
                    "max_drawdown": 10.0
                }
            }
        )
        
        if success and 'id' in strategy_response:
            strategy_id = strategy_response['id']
            self.created_resources['strategies'].append(strategy_id)
            
            # Test get single strategy
            self.run_test(
                "Get Single Strategy",
                "GET",
                f"strategies/{strategy_id}",
                200
            )
            
        # Get strategies
        success, _ = self.run_test(
            "Get Strategies",
            "GET",
            "strategies/",
            200 
        )
        
        return success

    def test_backtests_apis(self):
        """Test backtesting APIs"""
        print("\n📈 TESTING BACKTEST APIs")
        
        if not self.created_resources['strategies']:
            print("⏭️  Skipping backtest tests - no strategies created")
            return True
            
        # Run backtest
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
        end_date = datetime.now().isoformat()
        
        success, backtest_response = self.run_test(
            "Run Backtest",
            "POST",
            "backtests/run",
            200,
            data={
                "strategy_id": self.created_resources['strategies'][0],
                "asset": "BTC/USDT",
                "exchange": "Binance",
                "start_date": start_date,
                "end_date": end_date,
                "timeframe": "1D",
                "slippage": 0.001,
                "commission": 0.001
            }
        )
        
        if success and 'id' in backtest_response:
            backtest_id = backtest_response['id']
            self.created_resources['backtests'].append(backtest_id)
            
            # Test get single backtest
            self.run_test(
                "Get Single Backtest",
                "GET", 
                f"backtests/{backtest_id}",
                200
            )
        
        # Get backtests
        success, _ = self.run_test(
            "Get Backtests",
            "GET",
            "backtests/",
            200
        )
        
        return success

    def test_ai_chat_api(self):
        """Test AI chat functionality"""
        print("\n🤖 TESTING AI CHAT API")
        
        success, _ = self.run_test(
            "Send Chat Message",
            "POST",
            "chat/message",
            200,
            data={
                "message": "What is the current market sentiment for crypto?",
                "session_id": "test-session-123"
            }
        )
        
        return success

    def test_dashboard_api(self):
        """Test dashboard stats API"""
        print("\n📊 TESTING DASHBOARD API")
        
        success, stats = self.run_test(
            "Get Dashboard Stats",
            "GET", 
            "dashboard/stats",
            200
        )
        
        if success:
            required_fields = [
                'active_strategies', 'total_strategies', 'total_signals', 
                'total_backtests', 'current_regime', 'equity_curve',
                'system_health'
            ]
            for field in required_fields:
                if field not in stats:
                    print(f"❌ Missing required field: {field}")
                    return False
                    
        return success

    def test_health_endpoints(self):
        """Test basic health endpoints"""
        print("\n🏥 TESTING HEALTH ENDPOINTS")
        
        success, _ = self.run_test(
            "Root Endpoint",
            "GET",
            "",
            200,
            auth_required=False
        )
        
        success2, _ = self.run_test(
            "Health Endpoint",
            "GET",
            "health", 
            200,
            auth_required=False
        )
        
        return success and success2

    def cleanup_resources(self):
        """Clean up created test resources"""
        print("\n🧹 CLEANING UP TEST RESOURCES")
        
        # Delete in reverse dependency order
        for backtest_id in self.created_resources['backtests']:
            try:
                requests.delete(f"{self.base_url}/api/backtests/{backtest_id}", 
                               headers={'Authorization': f'Bearer {self.token}'})
            except: pass
                
        for strategy_id in self.created_resources['strategies']:
            try:
                requests.delete(f"{self.base_url}/api/strategies/{strategy_id}",
                               headers={'Authorization': f'Bearer {self.token}'})
            except: pass
                
        for signal_id in self.created_resources['signals']:
            try:
                requests.delete(f"{self.base_url}/api/signals/{signal_id}",
                               headers={'Authorization': f'Bearer {self.token}'})
            except: pass
                
        for feature_id in self.created_resources['features']:
            try:
                requests.delete(f"{self.base_url}/api/features/{feature_id}",
                               headers={'Authorization': f'Bearer {self.token}'})
            except: pass
                
        for feed_id in self.created_resources['feeds']:
            try:
                requests.delete(f"{self.base_url}/api/market-data/feeds/{feed_id}",
                               headers={'Authorization': f'Bearer {self.token}'})
            except: pass

def main():
    print("🚀 Starting Quantitative Research Laboratory API Tests")
    print(f"🌐 Testing against: https://backtester-ai.preview.emergentagent.com")
    
    tester = QuantLabAPITester()
    
    try:
        # Run comprehensive test suite
        tests = [
            tester.test_health_endpoints,
            tester.test_auth_flow,
            tester.test_dashboard_api, 
            tester.test_market_data_apis,
            tester.test_feature_generation_apis,
            tester.test_signals_apis,
            tester.test_strategies_apis,
            tester.test_backtests_apis,
            tester.test_ai_chat_api
        ]
        
        all_passed = True
        for test in tests:
            try:
                result = test()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Test failed with exception: {str(e)}")
                all_passed = False
                
        # Print final results
        print(f"\n📊 FINAL RESULTS:")
        print(f"Tests run: {tester.tests_run}")
        print(f"Tests passed: {tester.tests_passed}")
        print(f"Success rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "No tests run")
        
        if all_passed:
            print("🎉 All API endpoints are working correctly!")
        else:
            print("⚠️  Some tests failed - check logs above")
            
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"💥 Test suite failed: {str(e)}")
        return 1
    finally:
        # Clean up resources
        if tester.token:
            tester.cleanup_resources()

if __name__ == "__main__":
    sys.exit(main())