"""
Business logic for vendor selection and product normalization.
Implements enhanced decision rules for senior requirements.
"""

from typing import List, Optional
from models import NormalizedProduct, ProductResponse
from config import settings


class BusinessLogicService:
    """Service containing all business rules for vendor selection"""
    
    def select_best_vendor(self, products: List[NormalizedProduct]) -> ProductResponse:
        """
        Select the best vendor based on enhanced business rules:
        1. Filter valid products (price > 0, fresh data)
        2. Filter products with stock > 0
        3. Apply price-stock decision rule (10% price difference threshold)
        4. Return best vendor or OUT_OF_STOCK status
        """
        if not products:
            return ProductResponse(
                sku="UNKNOWN",
                status="OUT_OF_STOCK",
                vendors_checked=0
            )
            
        sku = products[0].sku
        vendors_checked = len(products)
        
        # Filter valid products only
        valid_products = [p for p in products if p.is_valid]
        
        if not valid_products:
            return ProductResponse(
                sku=sku,
                status="OUT_OF_STOCK",
                vendors_checked=vendors_checked
            )
            
        # Filter products with stock > 0
        in_stock_products = [p for p in valid_products if p.stock > 0]
        
        if not in_stock_products:
            return ProductResponse(
                sku=sku,
                status="OUT_OF_STOCK", 
                vendors_checked=vendors_checked
            )
            
        # Apply enhanced price-stock decision rule
        best_product = self._apply_enhanced_selection_rules(in_stock_products)
        
        return ProductResponse(
            sku=sku,
            best_vendor=best_product.vendor_name,
            price=best_product.price,
            stock=best_product.stock,
            status="AVAILABLE",
            vendors_checked=vendors_checked
        )
        
    def _apply_enhanced_selection_rules(self, products: List[NormalizedProduct]) -> NormalizedProduct:
        """
        Apply enhanced vendor selection rules:
        - If vendors differ in price by more than 10%, choose vendor with higher stock
        - Otherwise, choose vendor with lowest price
        """
        if len(products) == 1:
            return products[0]
            
        # Sort by price (ascending)
        products_by_price = sorted(products, key=lambda p: p.price)
        lowest_price_product = products_by_price[0]
        
        # Check if any other vendor has significantly different price
        for product in products_by_price[1:]:
            price_difference = (product.price - lowest_price_product.price) / lowest_price_product.price
            
            # If price difference > 10%, compare stock levels
            if price_difference > settings.PRICE_DIFFERENCE_THRESHOLD:
                if product.stock > lowest_price_product.stock:
                    # Higher stock wins even with higher price
                    return product
                    
        # Default: return lowest price vendor
        return lowest_price_product


# Global business logic service instance
business_logic_service = BusinessLogicService()