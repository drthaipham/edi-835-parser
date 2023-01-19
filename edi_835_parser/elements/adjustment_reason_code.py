from edi_835_parser.elements import Element, Code

# https://x12.org/codes/claim-adjustment-reason-codes
# imported 01-17-2023 
# list is truncated.. will do lookup outside of this module
adjustment_reason_codes = {
'1' : 'Deductible Amount | Start: 01/01/1995',
'2' : 'Coinsurance Amount | Start: 01/01/1995',
'3' : 'Co-payment Amount | Start: 01/01/1995'
}


class AdjustmentReasonCode(Element):

	def parser(self, value: str) -> Code:
		description = adjustment_reason_codes.get(value, None)
		return Code(value, description)
